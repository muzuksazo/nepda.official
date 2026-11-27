"""FR-008 & FR-014 project 7-day TTL enforcement, cleanup & startup orphan-job recovery."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import Settings
from .media_delivery import extract_object_key
from .project_store import ProjectStore
from .storage import StorageBackend
from .store import JobStore


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_project_expired(project: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """Return True if project's expires_at timestamp is at or before current UTC time."""
    exp = _parse_iso(project.get("expires_at"))
    if exp is None:
        return False
    cur = now or datetime.now(timezone.utc)
    return cur >= exp


def sync_project_status_with_job(
    project: Dict[str, Any],
    job_store: JobStore,
    project_store: ProjectStore,
) -> Dict[str, Any]:
    """Synchronize project.status immediately with its latest_job status."""
    jid = project.get("latest_job_id")
    if not jid or project.get("status") in {"HOOK_RENDERING", "HOOK_READY"}:
        return project
    job = job_store.get_job(jid)
    if not job:
        return project
    j_status = job.get("status")
    p_status = project.get("status")
    if j_status == "QC_READY" and p_status != "DELIVERABLE_READY":
        return project_store.update_project(project["project_id"], status="DELIVERABLE_READY")
    if j_status == "FAILED" and p_status == "RENDERING":
        return project_store.update_project(project["project_id"], status="FAILED")
    return project


def recover_orphaned_jobs(
    job_store: JobStore,
    project_store: ProjectStore,
) -> Dict[str, int]:
    """Mark in-flight jobs/hooks left behind by a previous server crash/restart as failed."""
    recovered_jobs = 0
    recovered_projects = 0
    recovered_hooks = 0

    active_jobs = job_store.list_jobs_by_status(("QUEUED", "RUNNING"))
    affected_job_ids: Set[str] = set()
    for job in active_jobs:
        job_store.update_job(
            job["id"],
            status="FAILED",
            stage=job.get("stage") or "FAILED",
            error="서버 재시작으로 인해 작업이 중단되었습니다. 다시 시도해 주세요.",
        )
        affected_job_ids.add(job["id"])
        recovered_jobs += 1

    for proj in project_store.list_projects_by_status(("RENDERING",)):
        if proj.get("latest_job_id") in affected_job_ids or not proj.get("latest_job_id"):
            project_store.update_project(proj["project_id"], status="FAILED")
            recovered_projects += 1

    active_hooks = project_store.list_hooks_by_status(("queued", "running"))
    hook_project_ids: Set[str] = set()
    for hk in active_hooks:
        project_store.update_hook(
            hk["hook_id"],
            status="failed",
            error="서버 재시작으로 인해 훅 생성이 중단되었습니다. 다시 시도해 주세요.",
        )
        hook_project_ids.add(hk["project_id"])
        recovered_hooks += 1

    for proj in project_store.list_projects_by_status(("HOOK_RENDERING",)):
        if proj["project_id"] in hook_project_ids or hook_project_ids:
            project_store.update_project(proj["project_id"], status="STORYBOARD_READY")
            recovered_projects += 1

    return {
        "recovered_jobs": recovered_jobs,
        "recovered_hooks": recovered_hooks,
        "recovered_projects": recovered_projects,
    }


def _collect_project_object_keys(
    project: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    hooks: List[Dict[str, Any]],
    storage: StorageBackend,
) -> Set[str]:
    keys: Set[str] = set()

    def _add(ref: Optional[str]) -> None:
        k = extract_object_key(ref, storage)
        if k:
            keys.add(k)

    for clip in (project.get("uploads") or {}).get("clips") or []:
        _add(clip.get("object_key"))

    for scn in scenarios:
        for frame in scn.get("storyboard_frames") or []:
            if isinstance(frame, dict):
                _add(frame.get("image_url"))

    for hk in hooks:
        files = hk.get("files") or {}
        for field in ("hook_video", "tts_audio", "subtitles_srt", "scenario_json"):
            _add(files.get(field))
        for sb in files.get("storyboard_images") or []:
            _add(sb)

    body = project.get("body") or {}
    for b_ref in (body.get("object_keys") or {}).values():
        _add(b_ref)

    thumb = project.get("thumbnail") or {}
    _add(thumb.get("object_key"))
    for c_ref in thumb.get("candidate_keys") or []:
        _add(c_ref)

    return keys


def prune_expired_data(
    project_store: ProjectStore,
    job_store: JobStore,
    storage: StorageBackend,
    settings: Settings,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    """Delete expired projects, their local/S3 files, and expired product_info_cache rows."""
    cur_iso = (now or datetime.now(timezone.utc)).isoformat()
    expired_projects = project_store.list_expired_projects(cur_iso)

    deleted_objects = 0
    delete_obj = getattr(storage, "delete_object", None)
    work_root = Path(settings.work_root).resolve()
    output_root = Path(settings.output_dir).resolve()

    for proj in expired_projects:
        pid = proj["project_id"]
        scenarios = project_store.list_scenarios(pid)
        hooks = project_store.list_hooks_for_project(pid)
        obj_keys = _collect_project_object_keys(proj, scenarios, hooks, storage)

        # Also collect artifacts from latest_job if present
        if proj.get("latest_job_id"):
            job = job_store.get_job(proj["latest_job_id"])
            if job:
                arts = job.get("artifacts") or {}
                for top_k in ("spec", "jobs", "credit_quote", "lint_report", "qa_strip"):
                    k = extract_object_key(arts.get(top_k), storage)
                    if k:
                        obj_keys.add(k)
                for r in arts.get("rendered") or []:
                    for rf in ("master_mp4", "clean_mp4", "srt"):
                        k = extract_object_key(r.get(rf), storage)
                        if k:
                            obj_keys.add(k)
                for t in arts.get("thumbnails") or []:
                    k = extract_object_key(t.get("url"), storage)
                    if k:
                        obj_keys.add(k)

        if callable(delete_obj):
            for key in obj_keys:
                if delete_obj(key):
                    deleted_objects += 1

        for base_dir in (work_root / pid, output_root / pid):
            if base_dir.exists() and base_dir.is_dir():
                shutil.rmtree(base_dir, ignore_errors=True)

        project_store.delete_project_cascade(pid)

    deleted_cache = project_store.delete_expired_product_info_cache(cur_iso)
    return {
        "expired_projects": len(expired_projects),
        "deleted_objects": deleted_objects,
        "deleted_cache_entries": deleted_cache,
    }
