"""Admin-only telemetry & cost inspection endpoints (`/v1/admin/usage/*`)."""

from __future__ import annotations

import hmac
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from .auth import SESSION_COOKIE_NAME, AuthenticatedUser, AuthenticationError, verify_session_token
from .config import Settings
from .project_store import ProjectStore
from .usage_telemetry import PRICING_VERSION, parse_pricing_overrides, pricing_catalog


def build_admin_router(settings: Settings, project_store: ProjectStore) -> APIRouter:
    """Create `/v1/admin/usage/*` routes gated by `ADMIN_EMAILS` or `API_BEARER_TOKEN`."""
    router = APIRouter(prefix="/v1/admin", tags=["Admin"])
    allowed_emails = {e.strip().lower() for e in (settings.admin_emails or "").split(",") if e.strip()}

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

    return router
