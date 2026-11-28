"""Admin-only telemetry, cost inspection, and Track A template management endpoints (`/v1/admin/*`)."""

from __future__ import annotations

import hmac
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import SESSION_COOKIE_NAME, AuthenticatedUser, AuthenticationError, verify_session_token
from .config import Settings
from .project_store import ProjectStore, persist_internal_accounts_to_storage
from .track_a_templates import (
    MAX_TEMPLATE_VIDEO_BYTES,
    TrackATemplateError,
    create_track_a_template,
    delete_track_a_template,
    get_track_a_template,
    list_track_a_templates,
    update_track_a_template,
)
from .usage_telemetry import PRICING_VERSION, parse_pricing_overrides, pricing_catalog


def _parse_multipart_bytes(
    content_type: str,
    body: bytes,
) -> Tuple[Dict[str, str], Dict[str, Tuple[str, bytes]]]:
    """Parse RFC 7578 multipart/form-data without external python-multipart dependency."""
    m = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))', content_type or "", flags=re.IGNORECASE)
    if not m:
        raise TrackATemplateError(
            400,
            "INVALID_REQUEST",
            "multipart/form-data 요청의 boundary 헤더가 누락되었습니다.",
        )
    boundary = (m.group(1) or m.group(2)).encode("latin-1")
    delimiter = b"--" + boundary
    fields: Dict[str, str] = {}
    files: Dict[str, Tuple[str, bytes]] = {}
    for part in body.split(delimiter)[1:]:
        if part.startswith(b"--"):
            break
        if part.startswith(b"\r\n"):
            part = part[2:]
        elif part.startswith(b"\n"):
            part = part[1:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        elif part.endswith(b"\n"):
            part = part[:-1]
        sep = b"\r\n\r\n" if b"\r\n\r\n" in part else b"\n\n"
        if sep not in part:
            continue
        raw_headers, payload = part.split(sep, 1)
        header_text = raw_headers.decode("utf-8", errors="replace")
        disp_line = ""
        for line in header_text.splitlines():
            if line.lower().startswith("content-disposition:"):
                disp_line = line.split(":", 1)[1].strip()
                break
        if not disp_line:
            continue
        name_m = re.search(r'name="([^"]+)"', disp_line)
        if not name_m:
            continue
        field_name = name_m.group(1)
        fn_star_m = re.search(r"filename\*=UTF-8''([^;\s]+)", disp_line, flags=re.IGNORECASE)
        fn_m = re.search(r'filename="([^"]*)"', disp_line)
        if fn_star_m is not None:
            files[field_name] = (unquote(fn_star_m.group(1)), payload)
        elif fn_m is not None:
            files[field_name] = (fn_m.group(1), payload)
        else:
            fields[field_name] = payload.decode("utf-8", errors="replace")
    return fields, files


def _raise_template_http_error(exc: TrackATemplateError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error": {"code": exc.code, "message": exc.message}},
    ) from exc


class SetInternalAccountRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    is_internal: bool = True
    note: Optional[str] = Field(default=None, max_length=200)


def build_admin_router(
    settings: Settings,
    project_store: ProjectStore,
    storage: Optional[Any] = None,
    template_storage: Optional[Any] = None,
) -> APIRouter:
    """Create `/v1/admin/*` routes gated by `ADMIN_EMAILS` or `API_BEARER_TOKEN`."""
    router = APIRouter(prefix="/v1/admin", tags=["Admin"])
    allowed_emails = {e.strip().lower() for e in (settings.admin_emails or "").split(",") if e.strip()}
    env_internal_emails = {e.strip().lower() for e in (settings.internal_test_emails or "").split(",") if e.strip()}

    def require_admin(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        token: Optional[str] = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :].strip()

        if token and settings.api_bearer_token and hmac.compare_digest(token, settings.api_bearer_token):
            return {"actor": "bearer_token", "dev_open_admin": False}

        session_token = token or request.cookies.get(SESSION_COOKIE_NAME)
        user: Optional[AuthenticatedUser] = None
        if session_token:
            try:
                user = verify_session_token(session_token, settings.session_secret)
            except AuthenticationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid or expired admin credentials."}},
                ) from exc

        if allowed_emails:
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": {"code": "UNAUTHORIZED", "message": "Admin login required."}},
                )
            if (user.email or "").strip().lower() not in allowed_emails:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin email allowlist access denied."}},
                )
            return {"actor": user.email, "dev_open_admin": False}

        if settings.api_bearer_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN if user else status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin API bearer token required."}},
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}},
            )
        return {"actor": user.email, "dev_open_admin": True}

    @router.get("/usage/summary")
    def usage_summary(
        days: int = Query(default=30, ge=1, le=365),
        limit: int = Query(default=50, ge=1, le=200),
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        summary = project_store.get_usage_summary(days=days, limit_projects=limit)
        overrides = parse_pricing_overrides(settings.usage_pricing_overrides_json)
        return {
            **summary,
            "days": days,
            "pricing_version": PRICING_VERSION,
            "pricing_table": pricing_catalog(overrides),
            "usd_krw_rate": settings.usd_krw_rate,
            "admin_actor": admin["actor"],
            "dev_open_admin": admin["dev_open_admin"],
        }

    @router.get("/usage/projects/{project_id}")
    def project_usage_detail(
        project_id: str,
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        detail = project_store.get_project_usage_detail(project_id)
        if detail["project"] is None and not detail["events"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": f"Project {project_id!r} not found"}},
            )
        return {
            **detail,
            "usd_krw_rate": settings.usd_krw_rate,
            "admin_actor": admin["actor"],
        }

    @router.get("/usage/events")
    def list_usage_events(
        limit: int = Query(default=100, ge=1, le=500),
        project_id: Optional[str] = Query(default=None),
        provider: Optional[str] = Query(default=None),
        stage: Optional[str] = Query(default=None),
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        events = project_store.list_usage_events(
            limit=limit,
            project_id=project_id,
            provider=provider,
            stage=stage,
        )
        return {
            "events": events,
            "count": len(events),
            "admin_actor": admin["actor"],
        }

    @router.get("/templates/track-a")
    def admin_list_track_a_templates(
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        templates = list_track_a_templates(
            settings,
            enabled_only=False,
            include_path=False,
            template_storage=template_storage,
        )
        return {
            "templates": templates,
            "admin_actor": admin["actor"],
        }

    @router.get("/templates/track-a/{template_id}/video")
    def admin_get_track_a_template_video(
        template_id: str,
        _admin: Dict[str, Any] = Depends(require_admin),
    ) -> FileResponse:
        try:
            entry = get_track_a_template(
                settings,
                template_id,
                include_path=True,
                template_storage=template_storage,
            )
        except TrackATemplateError as exc:
            _raise_template_http_error(exc)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "TEMPLATE_NOT_FOUND", "message": f"템플릿을 찾을 수 없습니다: {template_id}"}},
            )
        video_path = Path(entry["path"])
        if not video_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "TEMPLATE_NOT_FOUND", "message": "템플릿 영상 파일이 존재하지 않습니다."}},
            )
        return FileResponse(path=str(video_path), media_type="video/mp4", filename=entry["filename"])

    @router.post("/templates/track-a", status_code=status.HTTP_201_CREATED)
    async def admin_create_track_a_template(
        request: Request,
        _admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        ctype = request.headers.get("content-type", "")
        if "multipart/form-data" not in ctype.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_REQUEST", "message": "multipart/form-data 형식으로 업로드해 주세요."}},
            )
        body = await request.body()
        if len(body) > MAX_TEMPLATE_VIDEO_BYTES + 2 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_TEMPLATE_VIDEO", "message": "영상 파일 용량은 50MB 이하만 업로드할 수 있습니다."}},
            )
        try:
            fields, files = _parse_multipart_bytes(ctype, body)
            if "file" not in files:
                raise TrackATemplateError(400, "INVALID_TEMPLATE_VIDEO", "MP4 영상 파일(file)이 필요합니다.")
            fname, fbytes = files["file"]
            return create_track_a_template(
                settings,
                file_bytes=fbytes,
                filename=fname or "template.mp4",
                template_id=fields.get("id"),
                title=fields.get("title", ""),
                a_genre_archetype=fields.get("a_genre_archetype"),
                tags=fields.get("tags"),
                visual_summary=fields.get("visual_summary", ""),
                default_hook_captions=fields.get("default_hook_captions"),
                enabled=fields.get("enabled", True),
                template_storage=template_storage,
            )
        except TrackATemplateError as exc:
            _raise_template_http_error(exc)

    @router.patch("/templates/track-a/{template_id}")
    async def admin_update_track_a_template(
        template_id: str,
        request: Request,
        _admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        ctype = request.headers.get("content-type", "").lower()
        body = await request.body()
        if len(body) > MAX_TEMPLATE_VIDEO_BYTES + 2 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_TEMPLATE_VIDEO", "message": "영상 파일 용량은 50MB 이하만 업로드할 수 있습니다."}},
            )
        try:
            file_bytes: Optional[bytes] = None
            updates: Dict[str, Any] = {}
            if "multipart/form-data" in ctype:
                fields, files = _parse_multipart_bytes(request.headers.get("content-type", ""), body)
                updates.update(fields)
                if "file" in files and files["file"][1]:
                    file_bytes = files["file"][1]
            else:
                try:
                    raw = json.loads(body.decode("utf-8") or "{}")
                except Exception as exc:
                    raise TrackATemplateError(400, "INVALID_JSON", "올바른 JSON 요청 본문이 아닙니다.") from exc
                if not isinstance(raw, dict):
                    raise TrackATemplateError(400, "INVALID_REQUEST", "JSON 객체 형식이어야 합니다.")
                updates = raw
            return update_track_a_template(
                settings,
                template_id,
                updates=updates,
                file_bytes=file_bytes,
                template_storage=template_storage,
            )
        except TrackATemplateError as exc:
            _raise_template_http_error(exc)

    @router.delete("/templates/track-a/{template_id}")
    def admin_delete_track_a_template(
        template_id: str,
        _admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        try:
            return delete_track_a_template(
                settings,
                template_id,
                template_storage=template_storage,
            )
        except TrackATemplateError as exc:
            _raise_template_http_error(exc)

    def _accounts_payload(actor: str) -> Dict[str, Any]:
        accounts = project_store.list_admin_accounts(env_internal_emails=env_internal_emails)
        return {
            "accounts": accounts,
            "internal_count": sum(1 for a in accounts if a.get("is_internal")),
            "total_count": len(accounts),
            "admin_actor": actor,
        }

    @router.get("/accounts")
    def admin_list_accounts(
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        return _accounts_payload(admin["actor"])

    @router.post("/accounts/internal")
    def admin_set_internal_account(
        body: SetInternalAccountRequest = Body(...),
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        try:
            updated = project_store.set_internal_account(
                body.email,
                is_internal=body.is_internal,
                note=body.note,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_EMAIL", "message": str(exc)}},
            ) from exc
        persist_internal_accounts_to_storage(project_store, storage)
        return {
            "updated": updated,
            **_accounts_payload(admin["actor"]),
        }

    @router.delete("/accounts/internal/{email}")
    def admin_remove_internal_account(
        email: str,
        admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        try:
            updated = project_store.set_internal_account(email, is_internal=False)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_EMAIL", "message": str(exc)}},
            ) from exc
        persist_internal_accounts_to_storage(project_store, storage)
        return {
            "updated": updated,
            **_accounts_payload(admin["actor"]),
        }

    return router
