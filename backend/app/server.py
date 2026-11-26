"""FastAPI control-plane API for the google-genai shortform ad pipeline."""

from __future__ import annotations

import hmac
import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from google import genai
from pydantic import BaseModel, Field

from .config import Settings
from .genai_provider import GenAIMediaProvider
from .pipeline import CampaignRequest, ProductionPipeline
from .project_store import ProjectStore
from .projects_router import (
    GoogleTokenVerifier,
    ScenarioGenerator,
    StoryboardGenerator,
    build_projects_router,
)
from .storage import StorageBackend, build_storage
from .store import JobStore


class PresignRequest(BaseModel):
    object_key: str = Field(..., min_length=1)
    content_type: str = "video/mp4"
    expires_sec: int = Field(default=900, ge=60, le=86400)


class CreateJobRequest(BaseModel):
    campaign_id: str = Field(..., min_length=1)
    source_video: Optional[str] = None
    source_object_key: Optional[str] = None
    facts_path: Optional[str] = None
    facts_markdown: Optional[str] = None
    spec_path: Optional[str] = None
    spec_data: Optional[Dict[str, Any]] = None
    compare_abc_specs: Optional[List[str]] = None
    thumbs_spec_path: Optional[str] = None
    vo_manifest_path: Optional[str] = None
    track_archetype: str = "A_bgrade_reversal"
    resolution: str = "720p"
    normalize_cfr: bool = False
    clean_copy: bool = False
    dry_run: bool = False
    max_credits: Optional[int] = None
    concurrency: Optional[int] = None


def create_app(
    settings: Optional[Settings] = None,
    *,
    store: Optional[JobStore] = None,
    project_store: Optional[ProjectStore] = None,
    storage: Optional[StorageBackend] = None,
    provider_factory: Optional[Callable[[Settings], GenAIMediaProvider]] = None,
    google_token_verifier: Optional[GoogleTokenVerifier] = None,
    scenario_generator: Optional[ScenarioGenerator] = None,
    storyboard_generator: Optional[StoryboardGenerator] = None,
) -> FastAPI:
    cfg = settings or Settings()
    job_store = store or JobStore(cfg.db_path)
    proj_store = project_store or ProjectStore(cfg.db_path)
    storage_backend = storage or build_storage(cfg)
    pipeline = ProductionPipeline(
        cfg,
        job_store,
        storage=storage_backend,
        provider_factory=provider_factory,
    )
    executor = ThreadPoolExecutor(max_workers=max(1, cfg.concurrency))

    app = FastAPI(title="NAPDA Backend API", version="0.2.0")
    app.state.settings = cfg
    app.state.store = job_store
    app.state.project_store = proj_store
    app.state.storage = storage_backend
    app.state.pipeline = pipeline

    def require_bearer(authorization: Optional[str] = Header(default=None)) -> None:
        expected = cfg.api_bearer_token
        if not expected:
            return
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        token = authorization[len(prefix) :].strip()
        if not hmac.compare_digest(token, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

    def _run_bg(req: CampaignRequest, jid: str) -> None:
        try:
            pipeline.run_campaign(req, job_id=jid)
        except Exception as exc:
            job = job_store.get_job(jid)
            if job and job.get("status") != "FAILED":
                job_store.update_job(jid, status="FAILED", error=str(exc))

    def _retry_bg(jid: str, uid: str) -> None:
        try:
            pipeline.retry_unit(jid, uid)
        except Exception as exc:
            job = job_store.get_job(jid)
            if job:
                job_store.update_job(jid, status="FAILED", error=str(exc))

    @app.get("/health")
    def health() -> Dict[str, Any]:
        scripts_dir = cfg.resolved_scripts_dir
        bold_candidates = [
            os.environ.get("SHORTFORM_FONT_BOLD", "").strip(),
            os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        ]
        resolved_font = next((p for p in bold_candidates if p and os.path.exists(p)), None)
        has_interactions = hasattr(genai.Client, "interactions") or any(
            getattr(genai.Client(api_key="health-check-dummy"), "interactions", None) is not None
            for _ in [0]
        )
        return {
            "status": "ok",
            "auth_mode": cfg.auth_mode,
            "storage_backend": cfg.storage_backend,
            "google_genai_version": getattr(genai, "__version__", "unknown"),
            "interactions_api_available": bool(has_interactions),
            "ffmpeg": shutil.which("ffmpeg"),
            "ffprobe": shutil.which("ffprobe"),
            "font_resolved": resolved_font,
            "scripts_dir_exists": scripts_dir.exists(),
        }

    @app.post("/v1/uploads/presign", dependencies=[Depends(require_bearer)])
    def presign_upload(body: PresignRequest) -> Dict[str, str]:
        url = storage_backend.presign_upload(
            body.object_key,
            content_type=body.content_type,
            expires_sec=body.expires_sec,
        )
        return {"object_key": body.object_key, "upload_url": url}

    @app.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_bearer)])
    def create_job(body: CreateJobRequest) -> Dict[str, Any]:
        jid = f"job_{uuid.uuid4().hex[:12]}"
        req = CampaignRequest(**body.model_dump())
        record = job_store.create_job(jid, req.campaign_id, req.__dict__, status="QUEUED", stage="QUEUED")
        executor.submit(_run_bg, req, jid)
        return {"job_id": jid, "status": record["status"], "campaign_id": req.campaign_id}

    @app.get("/v1/jobs", dependencies=[Depends(require_bearer)])
    def list_jobs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> Dict[str, Any]:
        total = job_store.count_jobs()
        rows = job_store.list_jobs(limit=limit, offset=offset)
        has_more = (offset + len(rows)) < total
        return {
            "jobs": rows,
            "past_campaigns": job_store.list_past_campaigns(),
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": (offset + len(rows)) if has_more else None,
        }

    @app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_bearer)])
    def get_job(job_id: str) -> Dict[str, Any]:
        job = job_store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    @app.post(
        "/v1/jobs/{job_id}/retry-unit/{unit_id}",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_bearer)],
    )
    def retry_unit(job_id: str, unit_id: str) -> Dict[str, Any]:
        job = job_store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        executor.submit(_retry_bg, job_id, unit_id)
        return {"job_id": job_id, "unit_id": unit_id, "status": "QUEUED_RETRY"}

    app.include_router(
        build_projects_router(
            cfg,
            proj_store,
            job_store,
            storage_backend,
            pipeline,
            executor,
            google_token_verifier=google_token_verifier,
            scenario_generator=scenario_generator,
            storyboard_generator=storyboard_generator,
        )
    )

    return app


app = create_app()
