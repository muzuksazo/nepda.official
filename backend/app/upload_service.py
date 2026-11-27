"""FR-009 upload validation, real ffprobe inspection & multi-clip normalization helpers."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, status

from .config import Settings
from .project_schemas import UploadClipInput, UploadClipMetadata, UploadWarning
from .storage import StorageBackend

ProbeFn = Callable[[str], Dict[str, Any]]


def _api_error(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def recommended_framing(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "full-bleed"
    ratio = width / height
    if ratio < 0.72:
        return "full-bleed"
    if ratio <= 0.92:
        return "smart-crop"
    return "blur-bleed"


def probe_video_metadata(video_source: str) -> Dict[str, Any]:
    """Probe a local video file or signed HTTP URL using ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            video_source,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {(proc.stderr or proc.stdout).strip()}")
    raw = json.loads(proc.stdout or "{}")
    fmt = raw.get("format") or {}
    streams = raw.get("streams") or []
    vs = next((s for s in streams if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not vs:
        raise RuntimeError("No video stream found in uploaded file")

    dur = float(fmt.get("duration") or 0.0)
    width = int(vs.get("width") or 0)
    height = int(vs.get("height") or 0)
    if dur <= 0.0 or width <= 0 or height <= 0:
        raise RuntimeError("Invalid video duration or dimensions")

    fps = 30.0
    rate_raw = str(vs.get("r_frame_rate") or "30/1")
    if "/" in rate_raw:
        num, den = rate_raw.split("/", 1)
        try:
            fps = round(float(num) / max(float(den), 1.0), 3)
        except ValueError:
            fps = 30.0
    size_bytes = int(fmt.get("size") or 0)
    return {
        "duration_sec": dur,
        "size_bytes": size_bytes,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
    }


def validate_and_complete_uploads(
    project: Dict[str, Any],
    clips: List[UploadClipInput],
    *,
    storage: StorageBackend,
    settings: Settings,
    probe_fn: Optional[ProbeFn] = None,
) -> Dict[str, Any]:
    """Validate 1..20 uploaded clips against real storage objects + ffprobe and build manifest."""
    prober = probe_fn or probe_video_metadata
    sorted_clips = sorted(clips, key=lambda c: int(c.shot_no))

    warnings: List[UploadWarning] = []
    meta_list: List[UploadClipMetadata] = []
    normalized_clips: List[Dict[str, Any]] = []
    total_dur = 0.0

    resolve_local = getattr(storage, "resolve_local_path", None)
    head_obj = getattr(storage, "head_object", None)

    for clip in sorted_clips:
        local_candidate: Optional[Path] = None
        if clip.local_path and os.path.exists(clip.local_path):
            local_candidate = Path(clip.local_path).resolve()
        elif callable(resolve_local):
            local_candidate = resolve_local(clip.object_key)

        obj_meta = None
        if local_candidate is None and callable(head_obj):
            try:
                obj_meta = head_obj(clip.object_key)
            except Exception as exc:
                raise _api_error(
                    status.HTTP_502_BAD_GATEWAY,
                    "STORAGE_ERROR",
                    f"업로드 파일 메타데이터 조회에 실패했습니다 (shot {clip.shot_no}): {exc}",
                ) from exc

        real_exists = local_candidate is not None or obj_meta is not None
        if settings.require_uploaded_object_exists and not real_exists:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_UPLOAD_MEDIA",
                f"스토리지에 업로드된 영상을 찾을 수 없습니다 (shot {clip.shot_no}).",
                {"shot_no": clip.shot_no, "object_key": clip.object_key},
            )

        if local_candidate is not None:
            size_bytes = local_candidate.stat().st_size
        elif obj_meta is not None:
            size_bytes = obj_meta.size_bytes
        else:
            size_bytes = clip.file_size_bytes

        if size_bytes is not None and size_bytes > settings.max_upload_file_bytes:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_UPLOAD_LIMIT",
                f"파일 용량이 100MB 상한을 초과했습니다 (shot {clip.shot_no}).",
                {"max_bytes": settings.max_upload_file_bytes, "actual_bytes": size_bytes},
            )

        fps = 30.0
        has_audio = False
        if local_candidate is not None:
            try:
                probed = prober(str(local_candidate))
            except Exception as exc:
                raise _api_error(
                    status.HTTP_400_BAD_REQUEST,
                    "INVALID_UPLOAD_MEDIA",
                    f"업로드 영상 파일을 분석할 수 없습니다 (shot {clip.shot_no}): {exc}",
                    {"shot_no": clip.shot_no, "object_key": clip.object_key},
                ) from exc
            eff_dur = float(probed["duration_sec"])
            eff_w = int(probed["width"])
            eff_h = int(probed["height"])
            fps = float(probed.get("fps") or 30.0)
            has_audio = bool(probed.get("has_audio", False))
        elif obj_meta is not None:
            # S3 object exists: inspect via presigned GET URL unless client supplied complete probe values in tests
            try:
                signed_src = storage.presign_download(clip.object_key, expires_sec=300)
                probed = prober(signed_src)
                eff_dur = float(probed["duration_sec"])
                eff_w = int(probed["width"])
                eff_h = int(probed["height"])
                fps = float(probed.get("fps") or 30.0)
                has_audio = bool(probed.get("has_audio", False))
            except Exception as exc:
                raise _api_error(
                    status.HTTP_400_BAD_REQUEST,
                    "INVALID_UPLOAD_MEDIA",
                    f"업로드 영상 파일을 분석할 수 없습니다 (shot {clip.shot_no}): {exc}",
                    {"shot_no": clip.shot_no, "object_key": clip.object_key},
                ) from exc
        else:
            # Metadata-only test/dev submission when storage object is not physically uploaded yet
            if clip.duration_sec is None or clip.width is None or clip.height is None:
                raise _api_error(
                    status.HTTP_400_BAD_REQUEST,
                    "INVALID_UPLOAD_MEDIA",
                    f"영상 파일이 존재하지 않으며 길이·해상도 메타데이터가 누락되었습니다 (shot {clip.shot_no}).",
                    {"shot_no": clip.shot_no, "object_key": clip.object_key},
                )
            eff_dur = float(clip.duration_sec)
            eff_w = int(clip.width)
            eff_h = int(clip.height)

        total_dur += eff_dur
        framing = recommended_framing(eff_w, eff_h)

        if eff_w > eff_h:
            warnings.append(
                UploadWarning(
                    shot_no=clip.shot_no,
                    code="ASPECT_16_9",
                    message="가로 영상이라 세로 블러 배경(blur-bleed)으로 자동 보정됩니다.",
                )
            )

        meta_item = UploadClipMetadata(
            shot_no=clip.shot_no,
            object_key=clip.object_key,
            duration_sec=round(eff_dur, 2),
            width=eff_w,
            height=eff_h,
            recommended_framing=framing,
        )
        meta_list.append(meta_item)

        clip_dict = clip.model_dump()
        clip_dict["file_size_bytes"] = size_bytes
        clip_dict["duration_sec"] = round(eff_dur, 3)
        clip_dict["width"] = eff_w
        clip_dict["height"] = eff_h
        clip_dict["fps"] = fps
        clip_dict["has_audio"] = has_audio
        clip_dict["recommended_framing"] = framing
        normalized_clips.append(clip_dict)

    if total_dur < settings.min_upload_total_sec or total_dur > settings.max_upload_total_sec:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_UPLOAD_LIMIT",
            f"업로드 영상 총 길이는 {settings.min_upload_total_sec:.0f}~{settings.max_upload_total_sec:.0f}초여야 합니다 (현재 {total_dur:.1f}초).",
            {
                "min_sec": settings.min_upload_total_sec,
                "max_sec": settings.max_upload_total_sec,
                "total_sec": round(total_dur, 2),
            },
        )

    guide = project.get("filming_guide") or {}
    target_dur = float(guide.get("target_body_duration_sec") or 0.0)
    if target_dur > 0 and abs(total_dur - target_dur) > max(5.0, target_dur * 0.45):
        warnings.append(
            UploadWarning(
                shot_no=1,
                code="DURATION_DIFFERS_FROM_GUIDE",
                message=f"촬영 가이드 권장 길이({target_dur:.1f}초)와 달라 주요 구간이 자동 편집됩니다.",
            )
        )

    return {
        "project_id": project["project_id"],
        "status": "UPLOADS_READY",
        "upload_status": "WARNING" if warnings else "VALIDATED",
        "total_duration_sec": round(total_dur, 2),
        "warnings": [w_item.model_dump() for w_item in warnings],
        "metadata": [m.model_dump() for m in meta_list],
        "clips": normalized_clips,
    }
