"""Dedicated router for media streaming, FR-009 standalone body pipeline & FR-013 thumbnails."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from .auth import SESSION_COOKIE_NAME, AuthenticatedUser, AuthenticationError, verify_session_token
from .body_pipeline import build_body_video
from .config import Settings
from .media_delivery import (
    MediaTokenError,
    build_range_file_response,
    resolve_media_url,
    verify_media_token,
)
from .project_store import ProjectStore
from .retention import is_project_expired
from .storage import LocalStorageBackend, StorageBackend
from .store import JobStore
from .thumbnail_service import (
    DEFAULT_THUMBNAIL_STYLE,
    THUMBNAIL_STYLE_ALIASES,
    generate_project_thumbnail,
    normalize_thumbnail_style,
)
from .tts_service import TTSError, TTSProvider


class BodyScriptLineInput(BaseModel):
    narration: str = Field(..., min_length=1, max_length=240)
    caption: str = Field(..., min_length=1, max_length=80)


class CreateBodyRequest(BaseModel):
    target_duration_sec: Optional[float] = Field(default=None, ge=5.0, le=90.0)
    tts_enabled: bool = True
    voice_id: Optional[str] = None
    burn_captions: Optional[bool] = None
    lines: Optional[List[BodyScriptLineInput]] = Field(default=None, max_length=8)


class BodyBuildResponse(BaseModel):
    body_id: str
    project_id: str
    clip_count: int
    duration_sec: float
    width: int
    height: int
    fps: float
    lufs: Optional[float] = None
    tts_enabled: bool
    burn_captions: bool
    body_video_url: Optional[str] = None
    body_video_download_url: Optional[str] = None
    body_srt_url: Optional[str] = None
    body_audio_url: Optional[str] = None
    object_keys: dict
    created_at: str


class CreateThumbnailRequest(BaseModel):
    headline_lines: Optional[List[str]] = Field(default=None, min_length=1, max_length=3)
    badge: Optional[str] = Field(default=None, max_length=32)
    highlight_word: Optional[str] = Field(default=None, max_length=24)
    style: Literal[
        "invert-box",
        "white-label",
        "serif-outline",
        "pov-bar",
    ] = "invert-box"
    source_image_key: Optional[str] = None

    @field_validator("style", mode="before")
    @classmethod
    def _normalize_style(cls, value: object) -> object:
        if value is None:
            return DEFAULT_THUMBNAIL_STYLE
        if isinstance(value, str):
            mapped = THUMBNAIL_STYLE_ALIASES.get(value.strip().lower())
            if mapped is not None:
                return mapped
        return value


class ThumbnailBuildResponse(BaseModel):
    thumb_id: str
    project_id: str
    image_url: Optional[str] = None
    download_url: Optional[str] = None
    object_key: str
    safe_zone_1_1_ok: bool
    warnings: List[str] = Field(default_factory=list)
    headline_lines: List[str] = Field(default_factory=list)
    badge: Optional[str] = None
    highlight_word: Optional[str] = None
    style: str
    candidate_image_urls: List[str] = Field(default_factory=list)
    candidate_keys: List[str] = Field(default_factory=list)
    style_previews: Dict[str, str] = Field(default_factory=dict)
    created_at: str


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": {}}})


def build_pipeline_extras_router(
    settings: Settings,
    project_store: ProjectStore,
    job_store: JobStore,
    storage: StorageBackend,
    *,
    tts_provider: Optional[TTSProvider] = None,
) -> APIRouter:
    """Build `/v1/media/{token}`, `/v1/projects/{id}/body`, and `/v1/projects/{id}/thumbnail`."""
    router = APIRouter()

    def require_user(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> AuthenticatedUser:
        token: Optional[str] = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :].strip()
        if not token:
            token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "로그인이 필요합니다.")
        try:
            return verify_session_token(token, settings.session_secret)
        except AuthenticationError as exc:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", str(exc)) from exc

    def _get_owned_active_project(project_id: str, user: AuthenticatedUser) -> dict:
        proj = project_store.get_project(project_id, user_id=user.user_id)
        if not proj:
            raise _api_error(
                status.HTTP_404_NOT_FOUND,
                "PROJECT_NOT_FOUND",
                "프로젝트를 찾을 수 없거나 접근 권한이 없습니다.",
            )
        if is_project_expired(proj):
            raise _api_error(
                status.HTTP_410_GONE,
                "PROJECT_EXPIRED",
                "보관 기간(7일)이 만료된 프로젝트입니다.",
            )
        return proj

    def _to_body_response(manifest: dict) -> BodyBuildResponse:
        keys = manifest.get("object_keys") or {}
        return BodyBuildResponse(
            body_id=manifest["body_id"],
            project_id=manifest["project_id"],
            clip_count=int(manifest["clip_count"]),
            duration_sec=float(manifest["duration_sec"]),
            width=int(manifest["width"]),
            height=int(manifest["height"]),
            fps=float(manifest["fps"]),
            lufs=manifest.get("lufs"),
            tts_enabled=bool(manifest.get("tts_enabled", True)),
            burn_captions=bool(manifest.get("burn_captions", True)),
            body_video_url=resolve_media_url(keys.get("body_video"), storage=storage, settings=settings),
            body_video_download_url=resolve_media_url(
                keys.get("body_video"), storage=storage, settings=settings, download=True, filename="body.mp4"
            ),
            body_srt_url=resolve_media_url(
                keys.get("body_srt"), storage=storage, settings=settings, download=True, filename="body.srt"
            ),
            body_audio_url=resolve_media_url(keys.get("body_audio"), storage=storage, settings=settings),
            object_keys=keys,
            created_at=manifest["created_at"],
        )

    def _to_thumbnail_response(project_id: str, meta: dict) -> ThumbnailBuildResponse:
        cand_keys = list(meta.get("candidate_keys") or [])
        cand_urls = [
            u
            for u in (
                resolve_media_url(k, storage=storage, settings=settings)
                for k in cand_keys
            )
            if u
        ]
        image_url = resolve_media_url(meta.get("object_key"), storage=storage, settings=settings)
        active_style = normalize_thumbnail_style(meta.get("style"))
        preview_keys = meta.get("style_preview_keys") or {}
        style_previews: Dict[str, str] = {}
        if isinstance(preview_keys, dict):
            for st_key, obj_key in preview_keys.items():
                resolved = resolve_media_url(obj_key, storage=storage, settings=settings)
                if resolved:
                    style_previews[str(st_key)] = resolved
        if active_style not in style_previews and image_url:
            style_previews[active_style] = image_url
        return ThumbnailBuildResponse(
            thumb_id=meta["thumb_id"],
            project_id=project_id,
            image_url=image_url,
            download_url=resolve_media_url(
                meta.get("object_key"), storage=storage, settings=settings, download=True, filename="cover.png"
            ),
            object_key=meta["object_key"],
            safe_zone_1_1_ok=bool(meta.get("safe_zone_1_1_ok", False)),
            warnings=list(meta.get("warnings") or []),
            headline_lines=list(meta.get("headline_lines") or []),
            badge=meta.get("badge"),
            highlight_word=meta.get("highlight_word"),
            style=active_style,
            candidate_image_urls=cand_urls,
            candidate_keys=cand_keys,
            style_previews=style_previews,
            created_at=meta["created_at"],
        )

    @router.get("/v1/media/{token}", tags=["Delivery"])
    def serve_signed_media(
        token: str,
        download: bool = Query(default=False),
        range_header: Optional[str] = Header(default=None, alias="Range"),
    ) -> Response:
        try:
            object_key, filename = verify_media_token(token, settings.session_secret)
        except MediaTokenError as exc:
            raise _api_error(status.HTTP_403_FORBIDDEN, "INVALID_MEDIA_TOKEN", str(exc)) from exc

        resolve_local = getattr(storage, "resolve_local_path", None)
        local_path = resolve_local(object_key) if callable(resolve_local) else None
        if local_path is None:
            raise _api_error(status.HTTP_404_NOT_FOUND, "MEDIA_NOT_FOUND", "요청한 미디어 파일을 찾을 수 없습니다.")
        return build_range_file_response(local_path, range_header, download=download, filename=filename)

    @router.put("/v1/media/{token}", include_in_schema=False)
    async def upload_signed_local_media(token: str, request: Request) -> Response:
        try:
            object_key, _ = verify_media_token(token, settings.session_secret)
        except MediaTokenError as exc:
            raise _api_error(status.HTTP_403_FORBIDDEN, "INVALID_MEDIA_TOKEN", str(exc)) from exc

        if not isinstance(storage, LocalStorageBackend):
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "UNSUPPORTED_LOCAL_PUT",
                "원격 오브젝트 스토리지(S3/R2) 모드에서는 사전 서명 URL로 직접 업로드하세요.",
            )

        body = await request.body()
        if not body:
            raise _api_error(status.HTTP_400_BAD_REQUEST, "EMPTY_UPLOAD", "업로드된 파일 본문이 비어 있습니다.")
        if len(body) > settings.max_upload_file_bytes:
            raise _api_error(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "UPLOAD_TOO_LARGE",
                "파일 용량이 100MB 상한을 초과했습니다.",
            )

        dest = storage.local_path_for(object_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        return Response(status_code=status.HTTP_200_OK)

    @router.post("/v1/projects/{project_id}/body", response_model=BodyBuildResponse, tags=["Uploads"])
    def create_body_build(
        project_id: str,
        body: CreateBodyRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> BodyBuildResponse:
        proj = _get_owned_active_project(project_id, user)
        uploads = proj.get("uploads")
        if not uploads or not (uploads.get("clips") or []):
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_STATE",
                "본편을 생성하기 전에 원본 영상을 먼저 업로드해 주세요.",
            )
        scenarios = project_store.list_scenarios(project_id)
        custom_lines = [ln.model_dump() for ln in body.lines] if body.lines else None
        try:
            manifest = build_body_video(
                proj,
                storage=storage,
                settings=settings,
                tts_provider=tts_provider,
                target_duration_sec=body.target_duration_sec,
                tts_enabled=body.tts_enabled,
                voice_id=body.voice_id,
                burn_captions=body.burn_captions,
                custom_lines=custom_lines,
                scenarios=scenarios,
            )
        except TTSError as exc:
            raise _api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "TTS_UNAVAILABLE", str(exc)) from exc
        except ValueError as exc:
            raise _api_error(status.HTTP_400_BAD_REQUEST, "INVALID_STATE", str(exc)) from exc

        project_store.update_project(project_id, body=manifest)
        return _to_body_response(manifest)

    @router.get("/v1/projects/{project_id}/body", response_model=BodyBuildResponse, tags=["Uploads"])
    def get_body_build(
        project_id: str,
        user: AuthenticatedUser = Depends(require_user),
    ) -> BodyBuildResponse:
        proj = _get_owned_active_project(project_id, user)
        manifest = proj.get("body")
        if not manifest:
            raise _api_error(status.HTTP_404_NOT_FOUND, "BODY_NOT_FOUND", "생성된 본편 영상이 없습니다.")
        return _to_body_response(manifest)

    @router.post("/v1/projects/{project_id}/thumbnail", response_model=ThumbnailBuildResponse, tags=["Delivery"])
    def create_project_thumbnail(
        project_id: str,
        body: CreateThumbnailRequest,
        user: AuthenticatedUser = Depends(require_user),
    ) -> ThumbnailBuildResponse:
        proj = _get_owned_active_project(project_id, user)
        sel_id = proj.get("selected_scenario_id")
        scn = project_store.get_scenario(project_id, sel_id) if sel_id else None
        job = job_store.get_job(proj["latest_job_id"]) if proj.get("latest_job_id") else None
        meta = generate_project_thumbnail(
            proj,
            storage=storage,
            settings=settings,
            scenario=scn,
            job=job,
            headline_lines=body.headline_lines,
            badge=body.badge,
            highlight_word=body.highlight_word,
            style=body.style,
            source_image_key=body.source_image_key,
        )
        project_store.update_project(project_id, thumbnail=meta)
        return _to_thumbnail_response(project_id, meta)

    return router
