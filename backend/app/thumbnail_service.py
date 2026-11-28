"""FR-013 automated cover thumbnail builder, keyframe candidate extractor & 1:1 safe-zone validator."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image, ImageDraw

from .config import Settings
from .media_delivery import extract_object_key, thumbnail_object_key
from .storage import StorageBackend

logger = logging.getLogger("napda.thumbnail")

COVER_INTRO_DURATION_SEC: float = 0.4

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)

THUMBNAIL_STYLES: tuple[str, ...] = ("invert-box", "white-label", "serif-outline", "pov-bar")
FIGMA_THUMBNAIL_STYLES: tuple[str, ...] = THUMBNAIL_STYLES
DEFAULT_THUMBNAIL_STYLE: str = "invert-box"
THUMBNAIL_STYLE_ALIASES: Dict[str, str] = {
    "invert-box": "invert-box",
    "invert_box": "invert-box",
    "white-label": "white-label",
    "white_label": "white-label",
    "serif-outline": "serif-outline",
    "serif_outline": "serif-outline",
    "pov-bar": "pov-bar",
    "pov_bar": "pov-bar",
    # Legacy Pillow style aliases mapped to canonical 4 Figma Storybook styles
    "stroke": "serif-outline",
    "stroke_bold": "serif-outline",
    "blocks": "white-label",
    "line_blocks": "white-label",
    "card": "invert-box",
    "panel_card": "invert-box",
    "split": "pov-bar",
}


def normalize_thumbnail_style(style: Optional[str]) -> str:
    raw = str(style or "").strip().lower()
    return THUMBNAIL_STYLE_ALIASES.get(raw, DEFAULT_THUMBNAIL_STYLE)


def _build_thumb_spec_item(
    *,
    item_id: str,
    filename: str,
    chosen_bg: Path,
    clean_lines: List[str],
    clean_badge: str,
    style: str,
    clean_highlight: str = "",
) -> Dict[str, Any]:
    valid_style = normalize_thumbnail_style(style)
    thumb_item: Dict[str, Any] = {
        "id": item_id,
        "filename": filename,
        "layout": "figma",
        "figma_variant": valid_style,
        "image": str(chosen_bg),
        "strict_margin": True,
        "headline": {
            "style": valid_style,
            "lines": [{"text": ln} for ln in clean_lines],
            **({"highlight_word": clean_highlight} if clean_highlight else {}),
        },
    }
    if clean_badge:
        thumb_item["badge"] = clean_badge
    if clean_highlight:
        thumb_item["highlight_word"] = clean_highlight
    return thumb_item


def _strip_emojis(text: str) -> str:
    return EMOJI_RE.sub("", str(text or "")).strip()


def default_headline_lines(
    project: Dict[str, Any],
    scenario: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Derive 2 concise Korean thumbnail headline lines without emojis."""
    product = project.get("product") or {}
    name = _strip_emojis(str(product.get("name") or "제품 리뷰"))
    facts = [_strip_emojis(str(f)) for f in (product.get("verified_facts") or []) if _strip_emojis(str(f))]

    title_cand = _strip_emojis(str((scenario or {}).get("hook_title") or ""))
    if title_cand and len(title_cand) <= 14:
        line1 = title_cand
    else:
        line1 = name[:13]

    if facts:
        line2 = facts[0][:14]
    else:
        line2 = "실물 사용 확인"

    return [ln for ln in (line1, line2) if ln]


def extract_video_keyframes(
    video_path: Path,
    out_dir: Path,
    *,
    fractions: Sequence[float] = (0.15, 0.50, 0.82),
) -> List[Path]:
    """Extract representative 1080x1920 PNG keyframes from a video file using ffmpeg."""
    if not video_path.is_file():
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        dur = max(0.3, float((probe.stdout or "0").strip() or "0"))
    except ValueError:
        dur = 1.0

    extracted: List[Path] = []
    for idx, frac in enumerate(fractions, start=1):
        ts = min(max(0.05, dur * float(frac)), max(0.05, dur - 0.05))
        dst = out_dir / f"keyframe_{idx:02d}.png"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(dst),
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and dst.is_file() and dst.stat().st_size > 0:
            extracted.append(dst)
    return extracted


def _create_studio_fallback_bg(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1080, 1920), (18, 20, 26))
    draw = ImageDraw.Draw(im)
    for y in range(1920):
        t = y / 1919.0
        r = int(18 + 20 * (1.0 - t))
        g = int(20 + 24 * (1.0 - t))
        b = int(28 + 32 * (1.0 - t))
        draw.line([(0, y), (1080, y)], fill=(r, g, b))
    im.save(out_path, format="PNG")
    return out_path


def _resolve_local_from_ref(ref: Optional[str], dest_path: Path, storage: StorageBackend) -> Optional[Path]:
    if not ref:
        return None
    if os.path.exists(ref):
        return Path(ref).resolve()
    key = extract_object_key(ref, storage)
    if key:
        resolve_local = getattr(storage, "resolve_local_path", None)
        if callable(resolve_local):
            lp = resolve_local(key)
            if lp is not None:
                return lp
        try:
            storage.download_file(key, dest_path)
            if dest_path.is_file():
                return dest_path
        except Exception:
            return None
    return None


def prepend_thumbnail_to_video(
    cover_path: Path,
    source_video: Path,
    out_path: Path,
    *,
    duration_sec: float = COVER_INTRO_DURATION_SEC,
    ffmpeg_bin: Optional[str] = None,
) -> Path:
    """Prepend a crisp cover PNG intro frame (`duration_sec`) onto `source_video` (1080x1920 30fps)."""
    ffmpeg = (ffmpeg_bin or "").strip() or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg binary is required to prepend cover thumbnail to video")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        probe_candidate = Path(ffmpeg).with_name("ffprobe")
        if probe_candidate.exists():
            ffprobe = str(probe_candidate)

    has_audio = False
    if ffprobe:
        probe_proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(source_video),
            ],
            capture_output=True,
            text=True,
        )
        has_audio = probe_proc.returncode == 0 and bool((probe_proc.stdout or "").strip())

    dur = max(0.1, float(duration_sec or COVER_INTRO_DURATION_SEC))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if has_audio:
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v0];"
            "[2:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v1];"
            "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
            "[2:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-t",
            f"{dur:.3f}",
            "-framerate",
            "30",
            "-i",
            str(cover_path),
            "-f",
            "lavfi",
            "-t",
            f"{dur:.3f}",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-i",
            str(source_video),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
    else:
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v0];"
            "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v1];"
            "[v0][v1]concat=n=2:v=1:a=0[v]"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-t",
            f"{dur:.3f}",
            "-framerate",
            "30",
            "-i",
            str(cover_path),
            "-i",
            str(source_video),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_path),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not out_path.is_file():
        raise RuntimeError(f"ffmpeg failed prepending thumbnail cover: {(proc.stderr or proc.stdout or '')[:400]}")
    return out_path


def generate_project_thumbnail(
    project: Dict[str, Any],
    *,
    storage: StorageBackend,
    settings: Settings,
    scenario: Optional[Dict[str, Any]] = None,
    job: Optional[Dict[str, Any]] = None,
    headline_lines: Optional[Sequence[str]] = None,
    badge: Optional[str] = None,
    highlight_word: Optional[str] = None,
    style: str = DEFAULT_THUMBNAIL_STYLE,
    source_image_key: Optional[str] = None,
    include_style_previews: bool = True,
) -> Dict[str, Any]:
    """Build a 1080x1920 safe-zone validated cover PNG using `ad_thumbnail_builder.py`."""
    project_id = project["project_id"]
    thumb_id = f"thumb_{uuid.uuid4().hex[:10]}"
    work_dir = Path(settings.work_root).resolve() / project_id / "thumbnails" / thumb_id
    cand_dir = work_dir / "candidates"
    out_dir = work_dir / "out"
    cand_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    local_candidates: List[Path] = []
    if source_image_key:
        explicit = _resolve_local_from_ref(source_image_key, cand_dir / "explicit.png", storage)
        if explicit is not None:
            local_candidates.append(explicit)

    # Prefer clean_mp4 (subtitle/watermark-free) BEFORE master_mp4 for crisp cover keyframes
    rendered = ((job or {}).get("artifacts") or {}).get("rendered") or []
    if rendered and isinstance(rendered[0], dict):
        v_local = None
        for ref_key in ("clean_mp4", "master_mp4"):
            cand_ref = rendered[0].get(ref_key)
            if cand_ref:
                v_local = _resolve_local_from_ref(cand_ref, cand_dir / f"{ref_key}.mp4", storage)
                if v_local is not None:
                    break
        if v_local is not None:
            local_candidates.extend(extract_video_keyframes(v_local, cand_dir / "master_kf"))

    # Check standalone body.mp4 keyframes
    body_obj = project.get("body") or {}
    body_ref = (body_obj.get("object_keys") or {}).get("body_video")
    if body_ref:
        b_local = _resolve_local_from_ref(body_ref, cand_dir / "body.mp4", storage)
        if b_local is not None:
            local_candidates.extend(extract_video_keyframes(b_local, cand_dir / "body_kf"))

    # Check uploaded clip keyframes
    for idx, clip in enumerate((project.get("uploads") or {}).get("clips") or []):
        if len(local_candidates) >= 3:
            break
        c_ref = clip.get("local_path") or clip.get("object_key")
        c_local = _resolve_local_from_ref(c_ref, cand_dir / f"upload_{idx + 1:02d}.mp4", storage)
        if c_local is not None:
            local_candidates.extend(extract_video_keyframes(c_local, cand_dir / f"up_kf_{idx + 1:02d}", fractions=(0.25, 0.70)))

    # Check storyboard frames if local/stored
    for idx, frame in enumerate((scenario or {}).get("storyboard_frames") or []):
        if not isinstance(frame, dict):
            continue
        f_local = _resolve_local_from_ref(frame.get("image_url"), cand_dir / f"sb_{idx + 1:02d}.png", storage)
        if f_local is not None:
            local_candidates.append(f_local)

    # Deduplicate candidate files and ensure at least 1 background exists
    unique_cands: List[Path] = []
    seen_paths = set()
    for p in local_candidates:
        rp = str(p.resolve())
        if rp not in seen_paths and p.is_file():
            seen_paths.add(rp)
            unique_cands.append(p)

    if not unique_cands:
        unique_cands.append(_create_studio_fallback_bg(cand_dir / "fallback_studio.png"))

    # Upload candidate backgrounds for frontend picker
    candidate_keys: List[str] = []
    for idx, cpath in enumerate(unique_cands[:6], start=1):
        ckey = thumbnail_object_key(project_id, thumb_id, f"cand_{idx:02d}.png")
        storage.upload_file(cpath, ckey)
        candidate_keys.append(ckey)

    chosen_bg = unique_cands[0]
    clean_lines = [
        _strip_emojis(ln)[:36]
        for ln in (headline_lines or default_headline_lines(project, scenario))
        if _strip_emojis(ln)
    ][:3]
    if not clean_lines:
        clean_lines = [str((project.get("product") or {}).get("name") or "제품 확인")[:18]]

    clean_badge = _strip_emojis(badge)[:32] if badge else ""
    clean_highlight = _strip_emojis(highlight_word)[:24] if highlight_word else ""
    valid_style = normalize_thumbnail_style(style)

    thumb_items: List[Dict[str, Any]] = [
        _build_thumb_spec_item(
            item_id="cover",
            filename="cover.png",
            chosen_bg=chosen_bg,
            clean_lines=clean_lines,
            clean_badge=clean_badge,
            clean_highlight=clean_highlight,
            style=valid_style,
        )
    ]
    sibling_styles: List[str] = []
    if include_style_previews:
        for st in THUMBNAIL_STYLES:
            if st == valid_style:
                continue
            sibling_styles.append(st)
            thumb_items.append(
                _build_thumb_spec_item(
                    item_id=f"preview_{st}",
                    filename=f"preview_{st}.png",
                    chosen_bg=chosen_bg,
                    clean_lines=clean_lines,
                    clean_badge=clean_badge,
                    clean_highlight=clean_highlight,
                    style=st,
                )
            )

    spec_path = work_dir / "thumbs_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "canvas": {"width": 1080, "height": 1920},
                "strict_margin": True,
                "thumbnails": thumb_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    builder_script = settings.resolved_scripts_dir / "ad_thumbnail_builder.py"
    if not builder_script.is_file():
        raise FileNotFoundError(f"Missing thumbnail builder script: {builder_script}")
    proc = subprocess.run(
        [sys.executable, str(builder_script), "--spec", str(spec_path), "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ad_thumbnail_builder failed: {proc.stderr or proc.stdout}")
    result = json.loads(proc.stdout.strip())
    rendered_by_id = {
        str(entry.get("id") or ""): entry
        for entry in (result.get("thumbnails") or [])
        if isinstance(entry, dict)
    }
    thumb_info = rendered_by_id.get("cover") or (result.get("thumbnails") or [{}])[0]
    cover_path = Path(thumb_info["path"])

    cover_key = thumbnail_object_key(project_id, thumb_id, "cover.png")
    storage.upload_file(cover_path, cover_key)

    video_with_cover_key: Optional[str] = None
    cover_intro_sec: Optional[float] = None
    if rendered and isinstance(rendered[0], dict):
        master_ref = rendered[0].get("master_mp4")
        if master_ref:
            master_local = _resolve_local_from_ref(master_ref, work_dir / "master_src.mp4", storage)
            if master_local is not None:
                try:
                    with_cover_path = prepend_thumbnail_to_video(
                        cover_path,
                        master_local,
                        out_dir / "master_with_cover.mp4",
                        duration_sec=COVER_INTRO_DURATION_SEC,
                        ffmpeg_bin=settings.ffmpeg_bin,
                    )
                    cand_with_cover_key = thumbnail_object_key(project_id, thumb_id, "master_with_cover.mp4")
                    storage.upload_file(with_cover_path, cand_with_cover_key)
                    video_with_cover_key = cand_with_cover_key
                    cover_intro_sec = COVER_INTRO_DURATION_SEC
                except Exception as exc:
                    logger.warning("Failed to prepend thumbnail to master video (%s): %s", project_id, exc)

    style_preview_keys: Dict[str, str] = {valid_style: cover_key}
    for st in sibling_styles:
        entry = rendered_by_id.get(f"preview_{st}")
        if entry and entry.get("path"):
            p_path = Path(entry["path"])
            if p_path.is_file():
                p_key = thumbnail_object_key(project_id, thumb_id, f"preview_{st}.png")
                storage.upload_file(p_path, p_key)
                style_preview_keys[st] = p_key

    return {
        "thumb_id": thumb_id,
        "object_key": cover_key,
        "video_with_cover_key": video_with_cover_key,
        "cover_intro_sec": cover_intro_sec,
        "safe_zone_1_1_ok": bool(thumb_info.get("safe_zone_ok", False)),
        "warnings": list(thumb_info.get("warnings") or []),
        "headline_lines": clean_lines,
        "badge": clean_badge or None,
        "highlight_word": clean_highlight or None,
        "style": valid_style,
        "candidate_keys": candidate_keys,
        "style_preview_keys": style_preview_keys,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
