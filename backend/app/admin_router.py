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
from .media_delivery import resolve_media_url
from .project_store import ProjectStore, persist_internal_accounts_to_storage
from .thumbnail_service import normalize_thumbnail_style
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


STAGE_CATALOG: Dict[str, Dict[str, str]] = {
    "a_template": {
        "label": "A안 템플릿 매칭",
        "output_description": "A안 템플릿 선택 · 컷별 대사/자막 기획",
        "kind": "scenario",
    },
    "scenario_a": {
        "label": "A안 시나리오 기획",
        "output_description": "A안 시나리오 · 촬영가이드 텍스트",
        "kind": "scenario",
    },
    "scenario_b": {
        "label": "B안 시나리오 기획",
        "output_description": "B안 시나리오 · 촬영가이드 텍스트",
        "kind": "scenario",
    },
    "scenario_c": {
        "label": "C안 시나리오 기획",
        "output_description": "C안 시나리오 · 촬영가이드 텍스트",
        "kind": "scenario",
    },
    "storyboard": {
        "label": "콘티 이미지 생성",
        "output_description": "장면별 9:16 콘티 스틸 이미지 (PNG)",
        "kind": "image",
    },
    "ref_image": {
        "label": "참고·첫 프레임 이미지",
        "output_description": "톤·주인공 참고 또는 실사 첫 프레임 이미지 (JPG)",
        "kind": "image",
    },
    "video_clip": {
        "label": "훅 영상 클립 생성",
        "output_description": "장면별 AI 생성 훅 영상 클립 (MP4)",
        "kind": "video",
    },
    "tts": {
        "label": "훅 나레이션 (TTS)",
        "output_description": "장면별 훅 한국어 음성 오디오",
        "kind": "audio",
    },
    "body_script": {
        "label": "본편 대본·컷 기획",
        "output_description": "본편 나레이션 대본 · 자막 · 컷 편집안",
        "kind": "script",
    },
    "body_tts": {
        "label": "본편 나레이션 (TTS)",
        "output_description": "본편 줄별 한국어 음성 오디오",
        "kind": "audio",
    },
}


def _stage_meta(stage: str) -> Dict[str, str]:
    info = STAGE_CATALOG.get(str(stage or "").strip())
    if info:
        return dict(info)
    return {
        "label": str(stage or "unknown"),
        "output_description": "AI 호출 산출물",
        "kind": "other",
    }


def _extract_step_number(step_name: Optional[str]) -> Optional[int]:
    if not step_name:
        return None
    m = re.search(r"(\d+)$", str(step_name).strip())
    return int(m.group(1)) if m else None


def _match_event_to_artifact(
    ev: Dict[str, Any],
    artifacts: Optional[Dict[str, Any]],
    *,
    storage: Optional[Any],
    settings: Settings,
) -> Dict[str, Any]:
    """Match a single API usage telemetry event to its produced output artifact."""
    stage = str(ev.get("stage") or "").strip()
    step_name = str(ev.get("step_name") or "").strip()
    hook_type = (str(ev.get("hook_type") or "").strip().upper()) or None
    meta = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
    raw_obj_key = meta.get("object_key")
    obj_key = raw_obj_key.strip() if isinstance(raw_obj_key, str) and raw_obj_key.strip() else None

    resolved_preview = _resolve_admin_media(obj_key, storage=storage, settings=settings) if obj_key else None
    resolved_dl = (
        _resolve_admin_media(obj_key, storage=storage, settings=settings, download=True) if obj_key else None
    )

    step_num = _extract_step_number(step_name)
    stage_info = _stage_meta(stage)
    kind = stage_info["kind"]

    all_scenarios = [s for s in ((artifacts or {}).get("scenarios") or []) if isinstance(s, dict)]
    if hook_type:
        cand_scenarios = [s for s in all_scenarios if str(s.get("type") or "").upper() == hook_type] or all_scenarios
    else:
        cand_scenarios = all_scenarios

    all_hooks = [h for h in ((artifacts or {}).get("hooks") or []) if isinstance(h, dict)]
    cand_scn_ids = {s.get("scenario_id") for s in cand_scenarios if s.get("scenario_id")}
    matched_hooks = [h for h in all_hooks if h.get("scenario_id") in cand_scn_ids] or all_hooks
    matched_hook = matched_hooks[0] if matched_hooks else None

    def _result(
        *,
        label: str,
        media_type: str,
        preview_url: Optional[str] = None,
        download_url: Optional[str] = None,
        text_preview: Optional[str] = None,
        is_exact: bool = False,
    ) -> Dict[str, Any]:
        return {
            "kind": kind,
            "label": label,
            "media_type": media_type,
            "preview_url": preview_url,
            "download_url": download_url,
            "text_preview": text_preview,
            "object_key": obj_key,
            "is_exact": is_exact,
        }

    if stage == "storyboard":
        matched_frame: Optional[Dict[str, Any]] = None
        for scn in cand_scenarios:
            for fr in scn.get("storyboard_frames") or []:
                if not isinstance(fr, dict):
                    continue
                if step_num is not None and fr.get("beat_order") == step_num:
                    matched_frame = fr
                    break
            if matched_frame is not None:
                break
        label = f"{step_num}번 컷 콘티 이미지" if step_num is not None else "콘티 이미지"
        caption = (
            (matched_frame.get("caption") if matched_frame else None)
            or (str(meta.get("prompt") or "").strip()[:240] or None)
        )
        if resolved_preview:
            return _result(
                label=label,
                media_type="image",
                preview_url=resolved_preview,
                download_url=resolved_dl,
                text_preview=caption,
                is_exact=True,
            )
        if matched_frame and matched_frame.get("image_url"):
            return _result(
                label=label,
                media_type="image",
                preview_url=matched_frame.get("image_url"),
                text_preview=caption,
                is_exact=True,
            )
        return _result(label=label, media_type="text", text_preview=caption, is_exact=False)

    if stage == "ref_image":
        if step_name == "style_ref":
            label = "톤·주인공 참고 이미지"
        elif step_num is not None:
            label = f"{step_num}번 장면 첫 프레임 참고 이미지"
        else:
            label = "참고 이미지"
        prompt_text = str(meta.get("prompt") or "").strip()[:240] or None
        if resolved_preview:
            return _result(
                label=label,
                media_type="image",
                preview_url=resolved_preview,
                download_url=resolved_dl,
                text_preview=prompt_text,
                is_exact=True,
            )
        if matched_hook and matched_hook.get("video_url"):
            return _result(
                label="참고 이미지 (훅 영상 생성에 사용)",
                media_type="video",
                preview_url=matched_hook.get("video_url"),
                text_preview=prompt_text,
                is_exact=False,
            )
        return _result(label=label, media_type="text", text_preview=prompt_text, is_exact=False)

    if stage == "video_clip":
        base_label = f"{step_num}번 장면 AI 영상 클립" if step_num is not None else "훅 AI 영상 클립"
        meta_parts = []
        if meta.get("clip_sec") is not None:
            meta_parts.append(f"{meta.get('clip_sec')}s")
        if meta.get("resolution"):
            meta_parts.append(str(meta.get("resolution")))
        label = f"{base_label} ({' · '.join(meta_parts)})" if meta_parts else base_label
        prompt_text = str(meta.get("prompt") or "").strip()[:240] or None
        if resolved_preview:
            return _result(
                label=label,
                media_type="video",
                preview_url=resolved_preview,
                download_url=resolved_dl,
                text_preview=prompt_text,
                is_exact=True,
            )
        fallback_video = (matched_hook or {}).get("video_url") or (
            ((artifacts or {}).get("final_video") or {}).get("stream_url")
        )
        if fallback_video:
            fb_label = (
                f"{step_num}번 장면 AI 영상 (훅 영상에 합성됨)"
                if step_num is not None
                else "AI 영상 (훅 영상에 합성됨)"
            )
            return _result(
                label=fb_label,
                media_type="video",
                preview_url=fallback_video,
                text_preview=prompt_text,
                is_exact=False,
            )
        return _result(label=label, media_type="text", text_preview=prompt_text, is_exact=False)

    if stage == "tts":
        label = f"{step_num}번 장면 훅 나레이션 TTS" if step_num is not None else "훅 나레이션 TTS"
        voice = str(meta.get("voice") or "").strip()
        txt = str(meta.get("text") or "").strip()
        text_preview = f"[{voice}] {txt}" if (voice and txt) else (txt or None)
        if resolved_preview:
            return _result(
                label=label,
                media_type="audio",
                preview_url=resolved_preview,
                download_url=resolved_dl,
                text_preview=text_preview,
                is_exact=True,
            )
        if matched_hook and matched_hook.get("audio_url"):
            fb_label = (
                f"{step_num}번 장면 TTS (훅 통합 오디오)" if step_num is not None else "훅 통합 TTS 오디오"
            )
            return _result(
                label=fb_label,
                media_type="audio",
                preview_url=matched_hook.get("audio_url"),
                text_preview=text_preview,
                is_exact=False,
            )
        return _result(label=label, media_type="text", text_preview=text_preview, is_exact=False)

    if stage == "body_tts":
        label = f"본편 {step_num}번 줄 나레이션 TTS" if step_num is not None else "본편 나레이션 TTS"
        voice = str(meta.get("voice") or "").strip()
        txt = str(meta.get("text") or "").strip()
        text_preview = f"[{voice}] {txt}" if (voice and txt) else (txt or None)
        if resolved_preview:
            return _result(
                label=label,
                media_type="audio",
                preview_url=resolved_preview,
                download_url=resolved_dl,
                text_preview=text_preview,
                is_exact=True,
            )
        body_art = (artifacts or {}).get("body") or {}
        if body_art.get("audio_url"):
            return _result(
                label=label,
                media_type="audio",
                preview_url=body_art.get("audio_url"),
                text_preview=text_preview,
                is_exact=False,
            )
        if body_art.get("video_url"):
            return _result(
                label=f"{label} (본편 영상에 합성)",
                media_type="video",
                preview_url=body_art.get("video_url"),
                text_preview=text_preview,
                is_exact=False,
            )
        return _result(label=label, media_type="text", text_preview=text_preview, is_exact=False)

    if stage == "body_script":
        body_art = (artifacts or {}).get("body") or {}
        lines = (body_art.get("script") or {}).get("lines") or []
        snippets = [
            str(ln.get("narration") or ln.get("caption") or "").strip()
            for ln in lines
            if isinstance(ln, dict) and (ln.get("narration") or ln.get("caption"))
        ][:3]
        text_preview = (
            " / ".join(snippets)
            if snippets
            else (str(meta.get("response_preview") or "").strip()[:300] or None)
        )
        vid_url = body_art.get("video_url")
        srt_url = body_art.get("srt_url")
        return _result(
            label="본편 대본 · 컷 편집안",
            media_type="video" if vid_url else "text",
            preview_url=vid_url,
            download_url=srt_url,
            text_preview=text_preview,
            is_exact=bool(body_art),
        )

    if stage in ("a_template", "scenario_a", "scenario_b", "scenario_c"):
        letter = (
            "A"
            if stage in ("a_template", "scenario_a")
            else ("B" if stage == "scenario_b" else ("C" if stage == "scenario_c" else hook_type))
        )
        letter_scns = (
            [s for s in all_scenarios if str(s.get("type") or "").upper() == letter] if letter else cand_scenarios
        ) or cand_scenarios
        titles = [str(s.get("hook_title")) for s in letter_scns if s.get("hook_title")]
        if not titles and isinstance(meta.get("hook_titles"), list):
            titles = [str(t) for t in meta["hook_titles"] if t]
        first_sc = letter_scns[0] if letter_scns else None
        if letter and titles:
            label = f"{letter}안 시나리오: {titles[0]}"
        elif letter:
            label = f"{letter}안 시나리오 기획"
        else:
            label = stage_info["label"]
        parts = []
        if titles and len(titles) > 1:
            parts.append("후보: " + " / ".join(titles[:3]))
        if first_sc and first_sc.get("hook_summary"):
            parts.append(str(first_sc["hook_summary"]))
        elif first_sc and first_sc.get("beats"):
            parts.append(f"{len(first_sc['beats'])}컷 구성")
        elif meta.get("response_preview"):
            parts.append(str(meta["response_preview"])[:260])
        return _result(
            label=label,
            media_type="text",
            text_preview=" · ".join(parts) if parts else None,
            is_exact=True,
        )

    fallback_text = str(meta.get("prompt") or meta.get("text") or meta.get("response_preview") or "").strip()[:260]
    return _result(
        label=stage_info["label"],
        media_type="text",
        text_preview=fallback_text or None,
        is_exact=bool(resolved_preview),
        preview_url=resolved_preview,
        download_url=resolved_dl,
    )


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


def _resolve_admin_media(
    ref: Optional[str],
    *,
    storage: Optional[Any],
    settings: Settings,
    download: bool = False,
    filename: Optional[str] = None,
) -> Optional[str]:
    if not ref or not isinstance(ref, str):
        return None
    val = ref.strip()
    if not val:
        return None
    if storage is None:
        return val if val.startswith(("http://", "https://")) else None
    # Re-sign stored presigned R2 URLs so Admin links remain valid after TTL
    if val.startswith(("http://", "https://")) and "/projects/" in val:
        idx = val.find("projects/")
        if idx >= 0:
            clean_subkey = val[idx:].split("?", 1)[0]
            return resolve_media_url(
                clean_subkey,
                storage=storage,
                settings=settings,
                download=download,
                filename=filename,
            )
    return resolve_media_url(
        val,
        storage=storage,
        settings=settings,
        download=download,
        filename=filename,
    )


def _build_admin_project_artifacts(
    project: Optional[Dict[str, Any]],
    *,
    project_store: ProjectStore,
    job_store: Optional[Any],
    storage: Optional[Any],
    settings: Settings,
) -> Optional[Dict[str, Any]]:
    if not project:
        return None
    pid = str(project["project_id"])
    latest_job_id = project.get("latest_job_id")
    job = job_store.get_job(latest_job_id) if (job_store is not None and latest_job_id) else None
    arts = (job or {}).get("artifacts") or {}
    rendered = arts.get("rendered") or []
    first_r = rendered[0] if rendered and isinstance(rendered[0], dict) else None
    stored_thumb = project.get("thumbnail") if isinstance(project.get("thumbnail"), dict) else None

    final_video: Optional[Dict[str, Any]] = None
    if first_r:
        master_ref = first_r.get("master_key") or first_r.get("master_mp4")
        clean_ref = first_r.get("clean_key") or first_r.get("clean_mp4")
        srt_ref = first_r.get("srt_key") or first_r.get("srt")
        with_cover_ref = stored_thumb.get("video_with_cover_key") if stored_thumb else None
        active_ref = with_cover_ref or master_ref
        raw_dur = first_r.get("duration")
        cover_intro = float(stored_thumb.get("cover_intro_sec") or 0.0) if (with_cover_ref and stored_thumb) else 0.0
        eff_dur = round(float(raw_dur) + cover_intro, 3) if raw_dur is not None else None
        final_video = {
            "stream_url": _resolve_admin_media(active_ref, storage=storage, settings=settings),
            "download_url": _resolve_admin_media(
                active_ref, storage=storage, settings=settings, download=True, filename="napda_master.mp4"
            ),
            "raw_master_url": _resolve_admin_media(master_ref, storage=storage, settings=settings),
            "clean_url": _resolve_admin_media(
                clean_ref, storage=storage, settings=settings, download=True, filename="napda_clean.mp4"
            ),
            "srt_url": _resolve_admin_media(
                srt_ref, storage=storage, settings=settings, download=True, filename="napda_subtitles.srt"
            ),
            "duration_sec": eff_dur,
            "has_cover_intro": bool(with_cover_ref),
            "cover_intro_sec": cover_intro if with_cover_ref else 0.0,
            "voice": first_r.get("voice"),
            "job_id": latest_job_id,
            "job_status": (job or {}).get("status"),
            "warnings": list(arts.get("warnings") or []),
        }

    thumbnail: Optional[Dict[str, Any]] = None
    if stored_thumb:
        t_key = stored_thumb.get("object_key")
        thumbnail = {
            "image_url": _resolve_admin_media(t_key, storage=storage, settings=settings),
            "download_url": _resolve_admin_media(
                t_key, storage=storage, settings=settings, download=True, filename="cover.png"
            ),
            "style": normalize_thumbnail_style(stored_thumb.get("style")),
            "headline_lines": list(stored_thumb.get("headline_lines") or []),
            "badge": stored_thumb.get("badge"),
            "highlight_word": stored_thumb.get("highlight_word"),
            "has_video_with_cover": bool(stored_thumb.get("video_with_cover_key")),
            "safe_zone_1_1_ok": stored_thumb.get("safe_zone_1_1_ok"),
        }

    selected_id = project.get("selected_scenario_id")
    scenarios_out: list[Dict[str, Any]] = []
    for scn in project_store.list_scenarios(pid):
        frames_out = []
        for idx, frame in enumerate(scn.get("storyboard_frames") or [], start=1):
            if not isinstance(frame, dict):
                continue
            raw_img = frame.get("object_key") or frame.get("image_url")
            frames_out.append(
                {
                    "beat_order": frame.get("beat_order", idx),
                    "image_url": _resolve_admin_media(raw_img, storage=storage, settings=settings),
                    "caption": frame.get("caption"),
                }
            )
        scenarios_out.append(
            {
                "scenario_id": scn.get("scenario_id"),
                "type": scn.get("type"),
                "selected": bool(selected_id and scn.get("scenario_id") == selected_id),
                "hook_title": scn.get("hook_title"),
                "abstract_law": scn.get("abstract_law"),
                "genre": scn.get("genre"),
                "hook_summary": scn.get("hook_summary"),
                "beats": list(scn.get("beats") or []),
                "shooting_guide": scn.get("shooting_guide"),
                "storyboard_frames": frames_out,
            }
        )

    hooks_out: list[Dict[str, Any]] = []
    for hk in project_store.list_hooks_for_project(pid):
        hid = str(hk.get("hook_id") or "")
        files = hk.get("files") if isinstance(hk.get("files"), dict) else {}

        def _hook_url(field: str, dl: bool = False) -> Optional[str]:
            raw = files.get(field)
            if not raw or not isinstance(raw, str):
                return None
            if raw.startswith(("http://", "https://")) or "/" in raw:
                return _resolve_admin_media(raw, storage=storage, settings=settings, download=dl)
            obj_key = f"projects/{pid}/hooks/{hid}/{raw}"
            return _resolve_admin_media(obj_key, storage=storage, settings=settings, download=dl, filename=raw)

        hooks_out.append(
            {
                "hook_id": hid,
                "scenario_id": hk.get("scenario_id"),
                "status": hk.get("status"),
                "video_url": _hook_url("hook_video"),
                "audio_url": _hook_url("tts_audio"),
                "srt_url": _hook_url("subtitles_srt", dl=True),
                "scenario_json_url": _hook_url("scenario_json"),
                "error": hk.get("error"),
            }
        )

    body_out: Optional[Dict[str, Any]] = None
    body_obj = project.get("body")
    if isinstance(body_obj, dict) and body_obj:
        keys = body_obj.get("object_keys") if isinstance(body_obj.get("object_keys"), dict) else {}
        body_out = {
            "video_url": _resolve_admin_media(
                keys.get("body_video") or body_obj.get("video_key") or body_obj.get("video_path"),
                storage=storage,
                settings=settings,
            ),
            "srt_url": _resolve_admin_media(
                keys.get("body_srt") or body_obj.get("srt_key") or body_obj.get("srt_path"),
                storage=storage,
                settings=settings,
                download=True,
                filename="body.srt",
            ),
            "audio_url": _resolve_admin_media(
                keys.get("body_audio"),
                storage=storage,
                settings=settings,
            ),
            "duration_sec": body_obj.get("duration_sec"),
            "script": body_obj.get("script"),
        }

    uploads_out: list[Dict[str, Any]] = []
    for clip in (project.get("uploads") or {}).get("clips") or []:
        if not isinstance(clip, dict):
            continue
        uploads_out.append(
            {
                "clip_id": clip.get("clip_id"),
                "filename": clip.get("filename"),
                "duration_sec": clip.get("duration_sec"),
                "width": clip.get("width"),
                "height": clip.get("height"),
                "video_url": _resolve_admin_media(clip.get("object_key"), storage=storage, settings=settings),
            }
        )

    return {
        "product": project.get("product"),
        "final_video": final_video,
        "thumbnail": thumbnail,
        "scenarios": scenarios_out,
        "hooks": hooks_out,
        "body": body_out,
        "uploads": uploads_out,
    }


def build_admin_router(
    settings: Settings,
    project_store: ProjectStore,
    storage: Optional[Any] = None,
    template_storage: Optional[Any] = None,
    job_store: Optional[Any] = None,
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
        enriched_stages = []
        for row in summary.get("by_stage") or []:
            st_meta = _stage_meta(row.get("stage", ""))
            enriched_stages.append(
                {
                    **row,
                    "stage_label": st_meta["label"],
                    "output_description": st_meta["output_description"],
                }
            )
        enriched_projects = []
        for row in summary.get("recent_projects") or []:
            pid = str(row.get("project_id") or "")
            preview_meta: Dict[str, Any] = {
                "has_thumbnail": False,
                "thumbnail_url": None,
                "has_final_video": False,
                "storyboard_count": 0,
                "hook_count": 0,
            }
            if pid:
                try:
                    proj = project_store.get_project(pid)
                    thumb = (proj or {}).get("thumbnail") if isinstance((proj or {}).get("thumbnail"), dict) else None
                    thumb_key = thumb.get("object_key") if thumb else None
                    if thumb_key:
                        preview_meta["has_thumbnail"] = True
                        preview_meta["thumbnail_url"] = _resolve_admin_media(
                            thumb_key, storage=storage, settings=settings
                        )

                    scenarios = project_store.list_scenarios(pid)
                    sb_count = 0
                    first_sb_url: Optional[str] = None
                    for scn in scenarios:
                        for fr in scn.get("storyboard_frames") or []:
                            if not isinstance(fr, dict):
                                continue
                            sb_count += 1
                            if first_sb_url is None:
                                raw_img = fr.get("object_key") or fr.get("image_url")
                                first_sb_url = _resolve_admin_media(
                                    raw_img, storage=storage, settings=settings
                                )
                    preview_meta["storyboard_count"] = sb_count
                    if not preview_meta["thumbnail_url"] and first_sb_url:
                        preview_meta["thumbnail_url"] = first_sb_url

                    hooks = project_store.list_hooks_for_project(pid)
                    done_hooks = [h for h in hooks if str(h.get("status") or "").lower() == "done"]
                    preview_meta["hook_count"] = len(done_hooks) if done_hooks else len(hooks)

                    latest_job_id = (proj or {}).get("latest_job_id")
                    job = job_store.get_job(latest_job_id) if (job_store is not None and latest_job_id) else None
                    rendered = ((job or {}).get("artifacts") or {}).get("rendered") or []
                    first_r = rendered[0] if rendered and isinstance(rendered[0], dict) else None
                    if first_r and (first_r.get("master_key") or first_r.get("master_mp4")):
                        preview_meta["has_final_video"] = True
                except Exception:
                    pass
            enriched_projects.append({**row, **preview_meta})
        summary = {**summary, "by_stage": enriched_stages, "recent_projects": enriched_projects}
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
        full_project = project_store.get_project(project_id)
        artifacts = _build_admin_project_artifacts(
            full_project,
            project_store=project_store,
            job_store=job_store,
            storage=storage,
            settings=settings,
        )
        raw_events = detail.get("events") or []
        enriched_events = []
        stage_agg: Dict[str, Dict[str, Any]] = {}
        for ev in raw_events:
            st_key = str(ev.get("stage") or "")
            st_meta = _stage_meta(st_key)
            matched_artifact = _match_event_to_artifact(
                ev,
                artifacts,
                storage=storage,
                settings=settings,
            )
            enriched_events.append(
                {
                    **ev,
                    "stage_label": st_meta["label"],
                    "output_description": st_meta["output_description"],
                    "matched_artifact": matched_artifact,
                }
            )
            bucket = stage_agg.setdefault(
                st_key,
                {
                    "stage": st_key,
                    "stage_label": st_meta["label"],
                    "output_description": st_meta["output_description"],
                    "calls": 0,
                    "cache_hits": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
            bucket["calls"] += 1
            if ev.get("cache_hit"):
                bucket["cache_hits"] += 1
            if ev.get("estimated_cost_usd") is not None:
                bucket["estimated_cost_usd"] = round(
                    bucket["estimated_cost_usd"] + float(ev["estimated_cost_usd"]), 6
                )
        stage_breakdown = sorted(
            stage_agg.values(),
            key=lambda row: (row["estimated_cost_usd"], row["calls"]),
            reverse=True,
        )
        return {
            **detail,
            "events": enriched_events,
            "stage_breakdown": stage_breakdown,
            "artifacts": artifacts,
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
