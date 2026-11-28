"""Persistent Track A template manifest & video store shared by Admin API and Scenario/Render routers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Settings

TEMPLATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
MAX_TEMPLATE_VIDEO_BYTES = 50 * 1024 * 1024
MIN_TEMPLATE_DURATION_SEC = 2.0
MAX_TEMPLATE_DURATION_SEC = 30.0
DEFAULT_GENRE_ARCHETYPE = "mock_documentary"

BUNDLED_TRACK_A_DIR = (Path(__file__).resolve().parents[1] / "data" / "templates" / "track_a").resolve()

_MANIFEST_LOCK = threading.RLock()
_PROBE_CACHE: Dict[Tuple[str, int, int], Tuple[float, int, int]] = {}


class TrackATemplateError(Exception):
    """Domain error with HTTP status code & structured API error code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def resolve_managed_track_a_dir(settings: Settings) -> Path:
    """Resolve persistent managed Track A template directory (Modal volume or local data dir)."""
    if settings.track_a_template_dir and settings.track_a_template_dir.strip():
        return Path(settings.track_a_template_dir).expanduser().resolve()
    return (Path(settings.work_root).expanduser().resolve().parent / "templates" / "track_a").resolve()


def validate_template_id(template_id: str) -> str:
    clean = str(template_id or "").strip()
    if not TEMPLATE_ID_RE.fullmatch(clean):
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_ID",
            "템플릿 ID는 소문자·숫자·밑줄(_)·하이픈(-) 2~64자로만 구성할 수 있습니다.",
        )
    return clean


def _slugify_template_id(title: str) -> str:
    ascii_part = re.sub(r"[^a-z0-9]+", "_", str(title or "").lower()).strip("_")
    suffix = uuid.uuid4().hex[:6]
    base = f"a_{ascii_part[:32]}_{suffix}" if ascii_part else f"a_tpl_{suffix}"
    base = re.sub(r"_+", "_", base).strip("_")
    return base[:64]


def parse_tags_input(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                items = parsed if isinstance(parsed, list) else [text]
            except Exception:
                items = text.split(",")
        else:
            items = re.split(r"[,\n]+", text)
    else:
        items = [str(raw)]

    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        clean = str(item or "").strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            out.append(clean)
    return out


def parse_captions_input(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                items = parsed if isinstance(parsed, list) else [text]
            except Exception:
                items = text.splitlines()
        else:
            items = text.splitlines()
    else:
        items = [str(raw)]
    return [str(x).strip() for x in items if str(x or "").strip()]


def parse_bool_input(raw: Any, *, default: bool = True) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def probe_video_metadata(video_path: Path) -> Tuple[float, int, int, int]:
    """Probe MP4 duration, width, height, and file size with mtime/size caching."""
    st = video_path.stat()
    cache_key = (str(video_path.resolve()), st.st_mtime_ns, st.st_size)
    cached = _PROBE_CACHE.get(cache_key)
    if cached is not None:
        return cached[0], cached[1], cached[2], int(st.st_size)

    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            "업로드한 파일이 올바른 MP4 영상이 아닙니다. (ffprobe 분석 실패)",
        )
    try:
        raw = json.loads(proc.stdout or "{}")
    except Exception as exc:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            "영상 메타데이터를 읽을 수 없습니다.",
        ) from exc

    streams = raw.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v_stream:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            "영상 스트림이 포함되지 않은 파일입니다. MP4 동영상 파일을 올려 주세요.",
        )
    try:
        dur = round(float((raw.get("format") or {}).get("duration") or 0.0), 2)
    except (TypeError, ValueError):
        dur = 0.0
    width = int(v_stream.get("width") or 0)
    height = int(v_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            "영상 해상도를 확인할 수 없습니다.",
        )
    _PROBE_CACHE[cache_key] = (dur, width, height)
    return dur, width, height, int(st.st_size)


def validate_uploaded_video(video_path: Path) -> Tuple[float, int, int, int]:
    """Validate uploaded Track A template video size, video stream, and duration bounds."""
    if not video_path.is_file():
        raise TrackATemplateError(400, "INVALID_TEMPLATE_VIDEO", "업로드된 영상 파일을 찾을 수 없습니다.")
    size_bytes = video_path.stat().st_size
    if size_bytes <= 0:
        raise TrackATemplateError(400, "INVALID_TEMPLATE_VIDEO", "빈 파일은 업로드할 수 없습니다.")
    if size_bytes > MAX_TEMPLATE_VIDEO_BYTES:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            "영상 파일 용량은 50MB 이하만 업로드할 수 있습니다.",
        )
    dur, width, height, size_bytes = probe_video_metadata(video_path)
    if dur < MIN_TEMPLATE_DURATION_SEC or dur > MAX_TEMPLATE_DURATION_SEC:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            f"A안 템플릿 영상 길이는 {MIN_TEMPLATE_DURATION_SEC:.0f}~{MAX_TEMPLATE_DURATION_SEC:.0f}초여야 합니다. (현재 {dur:.2f}초)",
        )
    return dur, width, height, size_bytes


def _write_manifest_atomic(managed_dir: Path, raw_entries: List[Dict[str, Any]]) -> None:
    managed_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = managed_dir / "manifest.json"
    cleaned: List[Dict[str, Any]] = []
    for item in raw_entries:
        rec = {
            k: v
            for k, v in item.items()
            if k not in {"path", "video_url"}
        }
        cleaned.append(rec)
    payload = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".manifest_", suffix=".tmp", dir=str(managed_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, manifest_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _ensure_seeded(managed_dir: Path) -> None:
    """Seed managed_dir from bundled repo Track A templates on first read if uninitialized."""
    manifest_path = managed_dir / "manifest.json"
    if manifest_path.is_file():
        return
    bundled_manifest = BUNDLED_TRACK_A_DIR / "manifest.json"
    if not bundled_manifest.is_file():
        return
    if managed_dir.resolve() == BUNDLED_TRACK_A_DIR.resolve():
        return
    managed_dir.mkdir(parents=True, exist_ok=True)
    try:
        raw = json.loads(bundled_manifest.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(raw, list):
        return
    copied_entries: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fname = str(item.get("filename") or "").strip()
        if not fname:
            continue
        src_mp4 = (BUNDLED_TRACK_A_DIR / fname).resolve()
        if not src_mp4.is_file():
            continue
        dst_mp4 = (managed_dir / Path(fname).name).resolve()
        if not dst_mp4.is_file():
            shutil.copy2(src_mp4, dst_mp4)
        rec = dict(item)
        rec["filename"] = dst_mp4.name
        rec.setdefault("enabled", True)
        copied_entries.append(rec)
    _write_manifest_atomic(managed_dir, copied_entries)


def _read_raw_manifest(managed_dir: Path) -> List[Dict[str, Any]]:
    _ensure_seeded(managed_dir)
    manifest_path = managed_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _enrich_entry(raw: Dict[str, Any], managed_dir: Path) -> Optional[Dict[str, Any]]:
    tid = str(raw.get("id") or "").strip()
    fname = str(raw.get("filename") or "").strip()
    if not tid or not fname:
        return None
    video_path = (managed_dir / Path(fname).name).resolve()
    if not video_path.is_file():
        return None

    size_bytes = int(video_path.stat().st_size)
    dur = raw.get("duration_sec")
    width = raw.get("width")
    height = raw.get("height")
    if dur is None or width is None or height is None:
        try:
            p_dur, p_w, p_h, p_sz = probe_video_metadata(video_path)
            dur = float(dur) if dur is not None else p_dur
            width = int(width) if width is not None else p_w
            height = int(height) if height is not None else p_h
            size_bytes = p_sz
        except TrackATemplateError:
            dur = float(dur or 0.0)
            width = int(width or 0)
            height = int(height or 0)

    return {
        "id": tid,
        "filename": video_path.name,
        "title": str(raw.get("title") or tid).strip(),
        "duration_sec": round(float(dur or 0.0), 2),
        "width": int(width or 0),
        "height": int(height or 0),
        "size_bytes": size_bytes,
        "a_genre_archetype": str(raw.get("a_genre_archetype") or DEFAULT_GENRE_ARCHETYPE).strip() or DEFAULT_GENRE_ARCHETYPE,
        "tags": parse_tags_input(raw.get("tags")),
        "visual_summary": str(raw.get("visual_summary") or "").strip(),
        "default_hook_captions": parse_captions_input(raw.get("default_hook_captions")),
        "enabled": parse_bool_input(raw.get("enabled"), default=True),
        "video_url": f"/v1/admin/templates/track-a/{tid}/video",
        "path": str(video_path),
    }


def _to_public_dict(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in entry.items() if k != "path"}


def list_track_a_templates(
    settings: Settings,
    *,
    enabled_only: bool = False,
    include_path: bool = True,
) -> List[Dict[str, Any]]:
    """List normalized Track A templates from the persistent managed directory."""
    managed_dir = resolve_managed_track_a_dir(settings)
    with _MANIFEST_LOCK:
        raw_entries = _read_raw_manifest(managed_dir)
        out: List[Dict[str, Any]] = []
        for raw in raw_entries:
            enriched = _enrich_entry(raw, managed_dir)
            if not enriched:
                continue
            if enabled_only and not enriched["enabled"]:
                continue
            out.append(enriched if include_path else _to_public_dict(enriched))
        return out


def get_track_a_template(
    settings: Settings,
    template_id: str,
    *,
    include_path: bool = True,
) -> Optional[Dict[str, Any]]:
    tid = validate_template_id(template_id)
    managed_dir = resolve_managed_track_a_dir(settings)
    with _MANIFEST_LOCK:
        for raw in _read_raw_manifest(managed_dir):
            if str(raw.get("id") or "").strip() == tid:
                enriched = _enrich_entry(raw, managed_dir)
                if not enriched:
                    return None
                return enriched if include_path else _to_public_dict(enriched)
    return None


def create_track_a_template(
    settings: Settings,
    *,
    file_bytes: bytes,
    filename: str = "template.mp4",
    template_id: Optional[str] = None,
    title: str,
    a_genre_archetype: Optional[str] = None,
    tags: Any = None,
    visual_summary: str,
    default_hook_captions: Any = None,
    enabled: Any = True,
) -> Dict[str, Any]:
    clean_title = str(title or "").strip()
    if not clean_title:
        raise TrackATemplateError(400, "INVALID_REQUEST", "템플릿 제목(title)을 입력해 주세요.")
    clean_summary = str(visual_summary or "").strip()
    if not clean_summary:
        raise TrackATemplateError(400, "INVALID_REQUEST", "장면 설명(visual_summary)을 입력해 주세요.")
    if not file_bytes:
        raise TrackATemplateError(400, "INVALID_TEMPLATE_VIDEO", "MP4 영상 파일을 첨부해 주세요.")
    if len(file_bytes) > MAX_TEMPLATE_VIDEO_BYTES:
        raise TrackATemplateError(
            400,
            "INVALID_TEMPLATE_VIDEO",
            "영상 파일 용량은 50MB 이하만 업로드할 수 있습니다.",
        )

    raw_id = str(template_id or "").strip()
    tid = validate_template_id(raw_id) if raw_id else _slugify_template_id(clean_title)
    clean_genre = str(a_genre_archetype or DEFAULT_GENRE_ARCHETYPE).strip() or DEFAULT_GENRE_ARCHETYPE
    clean_tags = parse_tags_input(tags)
    clean_captions = parse_captions_input(default_hook_captions)
    is_enabled = parse_bool_input(enabled, default=True)

    managed_dir = resolve_managed_track_a_dir(settings)
    with _MANIFEST_LOCK:
        raw_entries = _read_raw_manifest(managed_dir)
        if any(str(e.get("id") or "").strip() == tid for e in raw_entries):
            raise TrackATemplateError(
                409,
                "TEMPLATE_ALREADY_EXISTS",
                f"이미 존재하는 템플릿 ID입니다: {tid}",
            )

        managed_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_mp4_str = tempfile.mkstemp(prefix=f".upload_{tid}_", suffix=".mp4", dir=str(managed_dir))
        tmp_mp4 = Path(tmp_mp4_str)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(file_bytes)
                fh.flush()
                os.fsync(fh.fileno())
            dur, width, height, size_bytes = validate_uploaded_video(tmp_mp4)
            target_filename = f"{tid}.mp4"
            target_path = (managed_dir / target_filename).resolve()
            os.replace(tmp_mp4, target_path)
        except Exception:
            try:
                tmp_mp4.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        new_raw: Dict[str, Any] = {
            "id": tid,
            "filename": target_filename,
            "title": clean_title,
            "duration_sec": dur,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "a_genre_archetype": clean_genre,
            "tags": clean_tags,
            "visual_summary": clean_summary,
            "default_hook_captions": clean_captions,
            "enabled": is_enabled,
        }
        raw_entries.append(new_raw)
        _write_manifest_atomic(managed_dir, raw_entries)
        enriched = _enrich_entry(new_raw, managed_dir)
        assert enriched is not None
        return _to_public_dict(enriched)


def update_track_a_template(
    settings: Settings,
    template_id: str,
    *,
    updates: Dict[str, Any],
    file_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    tid = validate_template_id(template_id)
    managed_dir = resolve_managed_track_a_dir(settings)
    with _MANIFEST_LOCK:
        raw_entries = _read_raw_manifest(managed_dir)
        idx = next((i for i, e in enumerate(raw_entries) if str(e.get("id") or "").strip() == tid), None)
        if idx is None:
            raise TrackATemplateError(404, "TEMPLATE_NOT_FOUND", f"템플릿을 찾을 수 없습니다: {tid}")

        entry = dict(raw_entries[idx])
        if file_bytes is not None:
            if len(file_bytes) == 0:
                raise TrackATemplateError(400, "INVALID_TEMPLATE_VIDEO", "빈 영상 파일은 업로드할 수 없습니다.")
            if len(file_bytes) > MAX_TEMPLATE_VIDEO_BYTES:
                raise TrackATemplateError(
                    400,
                    "INVALID_TEMPLATE_VIDEO",
                    "영상 파일 용량은 50MB 이하만 업로드할 수 있습니다.",
                )
            managed_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_mp4_str = tempfile.mkstemp(prefix=f".replace_{tid}_", suffix=".mp4", dir=str(managed_dir))
            tmp_mp4 = Path(tmp_mp4_str)
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(file_bytes)
                    fh.flush()
                    os.fsync(fh.fileno())
                dur, width, height, size_bytes = validate_uploaded_video(tmp_mp4)
                target_filename = Path(str(entry.get("filename") or f"{tid}.mp4")).name
                target_path = (managed_dir / target_filename).resolve()
                os.replace(tmp_mp4, target_path)
            except Exception:
                try:
                    tmp_mp4.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            entry["filename"] = target_filename
            entry["duration_sec"] = dur
            entry["width"] = width
            entry["height"] = height
            entry["size_bytes"] = size_bytes

        if "title" in updates and updates["title"] is not None:
            clean_title = str(updates["title"]).strip()
            if not clean_title:
                raise TrackATemplateError(400, "INVALID_REQUEST", "템플릿 제목(title)은 비워둘 수 없습니다.")
            entry["title"] = clean_title
        if "a_genre_archetype" in updates and updates["a_genre_archetype"] is not None:
            clean_genre = str(updates["a_genre_archetype"]).strip()
            if clean_genre:
                entry["a_genre_archetype"] = clean_genre
        if "tags" in updates and updates["tags"] is not None:
            entry["tags"] = parse_tags_input(updates["tags"])
        if "visual_summary" in updates and updates["visual_summary"] is not None:
            clean_summary = str(updates["visual_summary"]).strip()
            if not clean_summary:
                raise TrackATemplateError(400, "INVALID_REQUEST", "장면 설명(visual_summary)은 비워둘 수 없습니다.")
            entry["visual_summary"] = clean_summary
        if "default_hook_captions" in updates and updates["default_hook_captions"] is not None:
            entry["default_hook_captions"] = parse_captions_input(updates["default_hook_captions"])
        if "enabled" in updates and updates["enabled"] is not None:
            entry["enabled"] = parse_bool_input(updates["enabled"], default=True)

        raw_entries[idx] = entry
        _write_manifest_atomic(managed_dir, raw_entries)
        enriched = _enrich_entry(entry, managed_dir)
        assert enriched is not None
        return _to_public_dict(enriched)


def delete_track_a_template(settings: Settings, template_id: str) -> Dict[str, Any]:
    tid = validate_template_id(template_id)
    managed_dir = resolve_managed_track_a_dir(settings)
    with _MANIFEST_LOCK:
        raw_entries = _read_raw_manifest(managed_dir)
        idx = next((i for i, e in enumerate(raw_entries) if str(e.get("id") or "").strip() == tid), None)
        if idx is None:
            raise TrackATemplateError(404, "TEMPLATE_NOT_FOUND", f"템플릿을 찾을 수 없습니다: {tid}")

        removed = raw_entries.pop(idx)
        _write_manifest_atomic(managed_dir, raw_entries)
        fname = str(removed.get("filename") or "").strip()
        if fname:
            target = (managed_dir / Path(fname).name).resolve()
            if target.parent == managed_dir.resolve() and target.is_file():
                try:
                    target.unlink()
                except OSError:
                    pass
        return {"deleted": True, "id": tid}
