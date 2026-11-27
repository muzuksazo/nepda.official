"""FR-013 automated cover thumbnail builder, keyframe candidate extractor & 1:1 safe-zone validator."""

from __future__ import annotations

import json
import os
import re
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

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)

THUMBNAIL_STYLES: tuple[str, ...] = ("stroke_bold", "line_blocks", "panel_card")
THUMBNAIL_STYLE_ALIASES: Dict[str, str] = {
    "stroke": "stroke_bold",
    "stroke_bold": "stroke_bold",
    "blocks": "line_blocks",
    "line_blocks": "line_blocks",
    "card": "panel_card",
    "panel_card": "panel_card",
}


def normalize_thumbnail_style(style: Optional[str]) -> str:
    raw = str(style or "").strip().lower()
    return THUMBNAIL_STYLE_ALIASES.get(raw, "stroke_bold")


def _build_thumb_spec_item(
    *,
    item_id: str,
    filename: str,
    chosen_bg: Path,
    clean_lines: List[str],
    clean_badge: str,
    style: str,
) -> Dict[str, Any]:
    valid_style = normalize_thumbnail_style(style)
    line_entries = [
        {
            "text": ln,
            "color": (
                [214, 255, 63]
                if (idx == 1 and valid_style == "stroke_bold")
                else ([14, 18, 26] if valid_style == "line_blocks" else [255, 255, 255])
            ),
        }
        for idx, ln in enumerate(clean_lines)
    ]
    thumb_item: Dict[str, Any] = {
        "id": item_id,
        "filename": filename,
        "layout": "single",
        "image": str(chosen_bg),
        "strict_margin": True,
        "scrim": {"y_top": 450, "y_bottom": 960, "peak_alpha": 185, "edge_soft": 110},
        "headline": {
            "style": valid_style,
            "font_size": 88,
            "gap_after_pill": 22,
            "lines": line_entries,
        },
    }
    if clean_badge:
        thumb_item["pill"] = {
            "y": 510,
            "text": clean_badge,
            "fill": [214, 255, 63, 245],
            "outline": [10, 10, 10, 255],
            "text_color": [10, 10, 10, 255],
            "font_size": 36,
        }
    else:
        thumb_item["headline"]["y"] = 560
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


def generate_project_thumbnail(
    project: Dict[str, Any],
    *,
    storage: StorageBackend,
    settings: Settings,
    scenario: Optional[Dict[str, Any]] = None,
    job: Optional[Dict[str, Any]] = None,
    headline_lines: Optional[Sequence[str]] = None,
    badge: Optional[str] = None,
    style: str = "stroke_bold",
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

    # Check rendered master video keyframes first
    rendered = ((job or {}).get("artifacts") or {}).get("rendered") or []
    if rendered and isinstance(rendered[0], dict):
        v_ref = rendered[0].get("master_mp4") or rendered[0].get("clean_mp4")
        v_local = _resolve_local_from_ref(v_ref, cand_dir / "master.mp4", storage)
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
    clean_lines = [_strip_emojis(ln)[:18] for ln in (headline_lines or default_headline_lines(project, scenario)) if _strip_emojis(ln)][:2]
    if not clean_lines:
        clean_lines = [str((project.get("product") or {}).get("name") or "제품 확인")[:14]]

    clean_badge = _strip_emojis(badge)[:18] if badge else ""
    valid_style = normalize_thumbnail_style(style)

    thumb_items: List[Dict[str, Any]] = [
        _build_thumb_spec_item(
            item_id="cover",
            filename="cover.png",
            chosen_bg=chosen_bg,
            clean_lines=clean_lines,
            clean_badge=clean_badge,
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
        "safe_zone_1_1_ok": bool(thumb_info.get("safe_zone_ok", False)),
        "warnings": list(thumb_info.get("warnings") or []),
        "headline_lines": clean_lines,
        "badge": clean_badge or None,
        "style": valid_style,
        "candidate_keys": candidate_keys,
        "style_preview_keys": style_preview_keys,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
