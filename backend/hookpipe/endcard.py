"""$0.00 Pillow + FFmpeg Commercial Packshot End-Card generator for hookpipe."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

from .media import (
    AUDIO_ENCODE_ARGS,
    AUDIO_RATE,
    OUT_FPS,
    OUT_H,
    OUT_W,
    VIDEO_ENCODE_ARGS,
    MediaError,
    MediaTools,
    fill_filter,
    probe,
    run_ffmpeg,
)

logger = logging.getLogger("hookpipe.endcard")

DEFAULT_CTA_BADGE = "프로필 링크에서 확인 →"

_FONT_CANDIDATES: Tuple[Path, ...] = (
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Pretendard-ExtraBold.otf",
    Path("/usr/local/share/fonts/pretendard/Pretendard-ExtraBold.otf"),
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
)


def find_pretendard_font() -> Optional[Path]:
    """Return the first available Pretendard / Korean ExtraBold font path."""
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _load_font(font_path: Optional[Path], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path is not None:
        try:
            return ImageFont.truetype(str(font_path), size=size)
        except OSError as exc:
            logger.warning("폰트 로드 실패 (%s, %dpx): %s", font_path, size, exc)
    return ImageFont.load_default()


def _supports_glyph(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, ch: str) -> bool:
    try:
        mask = font.getmask(ch)
        return mask.size[0] > 0 and mask.size[1] > 0
    except Exception:
        return False


def _sanitize_arrow(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> str:
    if "→" in text and not _supports_glyph(font, "→"):
        return text.replace("→", ">")
    return text


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> float:
    if not text:
        return 0.0
    bbox = draw.textbbox((0, 0), text, font=font)
    return float(bbox[2] - bbox[0])


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> List[str]:
    """Wrap Korean/mixed text by spaces first, breaking long tokens by character."""
    clean = " ".join((text or "").split())
    if not clean:
        return []
    if _text_width(draw, clean, font) <= max_width:
        return [clean]

    words = clean.split(" ")
    lines: List[str] = []
    current = ""

    def _flush_chars(token: str, prefix: str) -> str:
        cur = prefix
        for ch in token:
            cand = f"{cur}{ch}"
            if cur and _text_width(draw, cand, font) > max_width:
                lines.append(cur)
                cur = ch
            else:
                cur = cand
        return cur

    for word in words:
        cand = f"{current} {word}".strip() if current else word
        if _text_width(draw, cand, font) <= max_width:
            current = cand
            continue
        if current:
            lines.append(current)
            current = ""
        if _text_width(draw, word, font) <= max_width:
            current = word
        else:
            current = _flush_chars(word, "")
    if current:
        lines.append(current)

    # Rebalance 2-line wraps if an unspaced string or greedy split left a tiny orphan tail.
    if len(lines) == 2 and len(lines[1]) <= 2 and " " in clean:
        best_pair: Optional[Tuple[str, str]] = None
        best_diff = 10**9
        for i in range(1, len(words)):
            left = " ".join(words[:i])
            right = " ".join(words[i:])
            lw = _text_width(draw, left, font)
            rw = _text_width(draw, right, font)
            if lw <= max_width and rw <= max_width and abs(lw - rw) < best_diff:
                best_diff = abs(lw - rw)
                best_pair = (left, right)
        if best_pair is not None:
            return [best_pair[0], best_pair[1]]
    return lines


def _fit_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Optional[Path],
    *,
    max_width: int,
    max_lines: int,
    start_size: int,
    min_size: int,
) -> Tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, int, List[str]]:
    clean = " ".join((text or "").split())
    if not clean:
        font = _load_font(font_path, min_size)
        return font, min_size, []

    for size in range(start_size, min_size - 1, -2):
        font = _load_font(font_path, size)
        lines = _wrap_text_to_width(draw, clean, font, max_width)
        if len(lines) <= max_lines and all(_text_width(draw, ln, font) <= max_width for ln in lines):
            return font, size, lines

    font = _load_font(font_path, min_size)
    lines = _wrap_text_to_width(draw, clean, font, max_width)
    if len(lines) > max_lines:
        kept = lines[:max_lines]
        tail = kept[-1]
        while tail and _text_width(draw, f"{tail}…", font) > max_width:
            tail = tail[:-1]
        kept[-1] = f"{tail}…" if tail else "…"
        lines = kept
    return font, min_size, lines


def _vertical_gradient(
    width: int,
    height: int,
    top_rgba: Tuple[int, int, int, int],
    bottom_rgba: Tuple[int, int, int, int],
) -> Image.Image:
    strip = Image.new("RGBA", (1, height))
    px = strip.load()
    denom = max(1, height - 1)
    for y in range(height):
        t = y / denom
        px[0, y] = (
            int(round(top_rgba[0] + (bottom_rgba[0] - top_rgba[0]) * t)),
            int(round(top_rgba[1] + (bottom_rgba[1] - top_rgba[1]) * t)),
            int(round(top_rgba[2] + (bottom_rgba[2] - top_rgba[2]) * t)),
            int(round(top_rgba[3] + (bottom_rgba[3] - top_rgba[3]) * t)),
        )
    return strip.resize((width, height), resample=Image.Resampling.BILINEAR)


def _sharpness_score(png_path: Path) -> float:
    with Image.open(png_path) as img:
        rgb = img.convert("RGB")
        w, h = rgb.size
        crop = rgb.crop((int(w * 0.20), int(h * 0.20), int(w * 0.80), int(h * 0.80)))
        edges = crop.convert("L").filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        return float(stat.mean[0]) + float(stat.stddev[0])


def extract_best_product_frame(body_video: Path, out_png: Path, tools: MediaTools) -> Optional[Path]:
    """Probe `body_video`, extract frames at 60%/74%/86%, and save the sharpest center-cropped frame."""
    if not body_video.is_file():
        return None
    info = probe(tools, body_video)
    if not info.has_video or info.duration <= 0.1:
        return None

    dur = float(info.duration)
    upper = max(0.3, dur - 0.2)
    timestamps = [max(0.3, min(upper, dur * frac)) for frac in (0.60, 0.74, 0.86)]
    if dur < 0.35:
        timestamps = [max(0.0, dur * frac) for frac in (0.50, 0.70, 0.85)]

    out_png.parent.mkdir(parents=True, exist_ok=True)
    cand_dir = out_png.parent / f"_cand_{uuid.uuid4().hex[:8]}"
    cand_dir.mkdir(parents=True, exist_ok=True)

    best_path: Optional[Path] = None
    best_score = -1.0
    try:
        for idx, ts in enumerate(timestamps, start=1):
            cand = cand_dir / f"cand_{idx:02d}.png"
            try:
                run_ffmpeg(
                    tools,
                    ["-ss", f"{ts:.3f}", "-i", str(body_video), "-frames:v", "1", "-q:v", "2", str(cand)],
                    timeout=60.0,
                )
            except MediaError:
                continue
            if not cand.is_file() or cand.stat().st_size <= 0:
                continue
            try:
                score = _sharpness_score(cand)
            except Exception:
                score = 0.0
            if best_path is None or score > best_score:
                best_score = score
                best_path = cand
        if best_path is None:
            return None
        shutil.copy2(best_path, out_png)
        return out_png if out_png.is_file() else None
    finally:
        shutil.rmtree(cand_dir, ignore_errors=True)


def render_packshot_png(
    bg_frame: Optional[Path],
    *,
    product_name: str,
    subhead: str,
    cta_badge: str,
    out_png: Path,
    width: int = OUT_W,
    height: int = OUT_H,
) -> Path:
    """Render a 9:16 studio commercial Packshot end-card PNG inside TikTok/Reels safe zone."""
    sx = width / 1080.0
    sy = height / 1920.0
    font_path = find_pretendard_font()

    # 1) Background: blurred product frame + dark gradient, or deep charcoal studio gradient
    src_img: Optional[Image.Image] = None
    if bg_frame is not None and bg_frame.is_file():
        try:
            with Image.open(bg_frame) as opened:
                src_img = opened.convert("RGB")
        except Exception as exc:
            logger.warning("엔드카드 배경 프레임 로드 실패 (%s): %s", bg_frame, exc)
            src_img = None

    if src_img is not None:
        bg_fitted = ImageOps.fit(src_img, (width, height), method=Image.Resampling.LANCZOS)
        bg_blurred = bg_fitted.filter(ImageFilter.GaussianBlur(radius=max(4, int(round(20 * min(sx, sy)))))).convert("RGBA")
        overlay = _vertical_gradient(width, height, (12, 15, 22, 175), (12, 15, 22, 232))
        canvas = Image.alpha_composite(bg_blurred, overlay)
    else:
        canvas = _vertical_gradient(width, height, (26, 31, 44, 255), (12, 15, 22, 255))
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        cx, cy = width // 2, int(round(580 * sy))
        rx, ry = int(round(420 * sx)), int(round(360 * sy))
        gdraw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(58, 74, 108, 70))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=max(10, int(round(90 * min(sx, sy))))))
        canvas = Image.alpha_composite(canvas, glow)

    # 2) Center-upper rounded product showcase inset (~780x580, radius=36, inside x=84..996, y=260..1500)
    card_w = int(round(780 * sx))
    card_h = int(round(580 * sy))
    card_x = (width - card_w) // 2
    card_y = int(round(285 * sy))
    card_r = max(8, int(round(36 * min(sx, sy))))

    shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sh_off = int(round(14 * sy))
    sdraw.rounded_rectangle(
        (card_x, card_y + sh_off, card_x + card_w, card_y + card_h + sh_off),
        radius=card_r,
        fill=(0, 0, 0, 140),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(4, int(round(24 * min(sx, sy))))))
    canvas = Image.alpha_composite(canvas, shadow_layer)

    if src_img is not None:
        inset_rgb = ImageOps.fit(src_img, (card_w, card_h), method=Image.Resampling.LANCZOS).convert("RGBA")
    else:
        inset_rgb = _vertical_gradient(card_w, card_h, (38, 45, 62, 255), (20, 24, 34, 255))

    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=card_r, fill=255)
    card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    card_layer.paste(inset_rgb, (card_x, card_y), mask)
    canvas = Image.alpha_composite(canvas, card_layer)

    border_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(border_layer)
    bdraw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=card_r,
        outline=(255, 255, 255, 70),
        width=max(1, int(round(2 * min(sx, sy)))),
    )
    canvas = Image.alpha_composite(canvas, border_layer)

    # 3) Measure typography stack (Hero Title -> Subhead -> CTA Pill) inside safe zone y <= 1500
    measure_draw = ImageDraw.Draw(canvas)
    title_text = (product_name or "").strip() or "제품 확인하기"
    title_font, title_sz, title_lines = _fit_wrapped_text(
        measure_draw,
        title_text,
        font_path,
        max_width=int(round(880 * sx)),
        max_lines=2,
        start_size=max(20, int(round(68 * sy))),
        min_size=max(16, int(round(44 * sy))),
    )

    sub_text = (subhead or "").strip()
    sub_font, sub_sz, sub_lines = _fit_wrapped_text(
        measure_draw,
        sub_text,
        font_path,
        max_width=int(round(860 * sx)),
        max_lines=2,
        start_size=max(14, int(round(36 * sy))),
        min_size=max(12, int(round(28 * sy))),
    )

    raw_cta = (cta_badge or "").strip() or DEFAULT_CTA_BADGE
    cta_probe_font = _load_font(font_path, max(16, int(round(40 * sy))))
    cta_text = _sanitize_arrow(raw_cta, cta_probe_font)
    cta_font, cta_sz, cta_lines = _fit_wrapped_text(
        measure_draw,
        cta_text,
        font_path,
        max_width=int(round(760 * sx)),
        max_lines=1,
        start_size=max(16, int(round(40 * sy))),
        min_size=max(14, int(round(30 * sy))),
    )
    cta_line = cta_lines[0] if cta_lines else _sanitize_arrow(DEFAULT_CTA_BADGE, cta_font)

    def _measure_lines(lines: Sequence[str], fnt: ImageFont.FreeTypeFont | ImageFont.ImageFont, gap: int) -> Tuple[List[Tuple[str, Tuple[int, int, int, int]]], int]:
        items = []
        total_h = 0
        for i, ln in enumerate(lines):
            bb = measure_draw.textbbox((0, 0), ln, font=fnt)
            items.append((ln, bb))
            total_h += (bb[3] - bb[1]) + (gap if i > 0 else 0)
        return items, total_h

    title_gap = max(4, int(round(title_sz * 0.28)))
    sub_gap = max(4, int(round(sub_sz * 0.30)))
    title_items, title_h = _measure_lines(title_lines, title_font, title_gap)
    sub_items, sub_h = _measure_lines(sub_lines, sub_font, sub_gap)

    cta_bb = measure_draw.textbbox((0, 0), cta_line, font=cta_font)
    cta_tw = cta_bb[2] - cta_bb[0]
    cta_th = cta_bb[3] - cta_bb[1]
    pad_x = int(round(48 * sx))
    pad_y = int(round(22 * sy))
    pill_w = min(int(round(880 * sx)), cta_tw + pad_x * 2)
    pill_h = cta_th + pad_y * 2

    gap_title_sub = int(round(26 * sy)) if sub_items else 0
    gap_to_pill = int(round(52 * sy))
    stack_h = title_h + gap_title_sub + sub_h + gap_to_pill + pill_h

    title_y = card_y + card_h + int(round(58 * sy))
    safe_bottom = int(round(1485 * sy))
    if title_y + stack_h > safe_bottom:
        title_y = max(card_y + card_h + int(round(24 * sy)), safe_bottom - stack_h)

    # 4) Draw Title + Subhead with subtle dark shadow
    text_shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ts_draw = ImageDraw.Draw(text_shadow)
    text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(text_layer)

    cur_y = title_y
    for i, (ln, bb) in enumerate(title_items):
        if i > 0:
            cur_y += title_gap
        lw = bb[2] - bb[0]
        lh = bb[3] - bb[1]
        tx = (width - lw) / 2.0 - bb[0]
        ty = cur_y - bb[1]
        ts_draw.text((tx, ty + max(2, int(round(3 * sy)))), ln, font=title_font, fill=(0, 0, 0, 190))
        t_draw.text((tx, ty), ln, font=title_font, fill=(255, 255, 255, 255))
        cur_y += lh

    if sub_items:
        cur_y += gap_title_sub
        for i, (ln, bb) in enumerate(sub_items):
            if i > 0:
                cur_y += sub_gap
            lw = bb[2] - bb[0]
            lh = bb[3] - bb[1]
            tx = (width - lw) / 2.0 - bb[0]
            ty = cur_y - bb[1]
            ts_draw.text((tx, ty + max(1, int(round(2 * sy)))), ln, font=sub_font, fill=(0, 0, 0, 165))
            t_draw.text((tx, ty), ln, font=sub_font, fill=(229, 231, 235, 245))
            cur_y += lh

    text_shadow = text_shadow.filter(ImageFilter.GaussianBlur(radius=max(1, int(round(4 * min(sx, sy))))))
    canvas = Image.alpha_composite(canvas, text_shadow)
    canvas = Image.alpha_composite(canvas, text_layer)

    # 5) High-contrast rounded CTA pill (#FFE047 fill, #111317 text)
    pill_x = (width - pill_w) // 2
    pill_y = cur_y + gap_to_pill
    pill_r = min(max(12, int(round(44 * min(sx, sy)))), pill_h // 2)

    pill_glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pg_draw = ImageDraw.Draw(pill_glow)
    pg_draw.rounded_rectangle(
        (pill_x - 4, pill_y - 2, pill_x + pill_w + 4, pill_y + pill_h + 6),
        radius=pill_r + 4,
        fill=(255, 224, 71, 68),
    )
    pill_glow = pill_glow.filter(ImageFilter.GaussianBlur(radius=max(4, int(round(16 * min(sx, sy))))))
    canvas = Image.alpha_composite(canvas, pill_glow)

    pill_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(pill_layer)
    p_draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=pill_r,
        fill=(255, 224, 71, 255),
        outline=(255, 246, 179, 210),
        width=max(1, int(round(2 * min(sx, sy)))),
    )
    cta_tx = pill_x + (pill_w - cta_tw) / 2.0 - cta_bb[0]
    cta_ty = pill_y + (pill_h - cta_th) / 2.0 - cta_bb[1]
    p_draw.text((cta_tx, cta_ty), cta_line, font=cta_font, fill=(17, 19, 23, 255))
    canvas = Image.alpha_composite(canvas, pill_layer)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_png, format="PNG")
    return out_png


def build_endcard_clip(
    card_png: Path,
    out_mp4: Path,
    *,
    duration_sec: float = 2.0,
    tools: MediaTools,
) -> Path:
    """Encode a still Packshot PNG into a 1080x1920 30fps MP4 clip with fade-in/out and stereo silence."""
    if not card_png.is_file():
        raise MediaError(f"엔드카드 이미지가 없습니다: {card_png}")
    dur = max(0.5, float(duration_sec))
    fade_out_st = max(0.0, dur - 0.30)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},fps={OUT_FPS},setsar=1,format=yuv420p,"
        f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out_st:.3f}:d=0.30"
    )
    run_ffmpeg(
        tools,
        [
            "-loop", "1", "-t", f"{dur:.3f}", "-i", str(card_png),
            "-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
            "-vf", vf,
            "-map", "0:v", "-map", "1:a",
            *VIDEO_ENCODE_ARGS,
            *AUDIO_ENCODE_ARGS,
            "-t", f"{dur:.3f}",
            str(out_mp4),
        ],
    )
    if not out_mp4.is_file() or out_mp4.stat().st_size <= 0:
        raise MediaError("엔드카드 클립 생성 결과가 비어 있습니다.")
    return out_mp4


def append_endcard(
    final_mp4: Path,
    endcard_mp4: Path,
    *,
    tools: MediaTools,
    tmp_dir: Path,
) -> float:
    """Append `endcard_mp4` onto `final_mp4`, atomically replace `final_mp4`, and return probed duration."""
    if not final_mp4.is_file():
        raise MediaError(f"최종 영상이 없습니다: {final_mp4}")
    if not endcard_mp4.is_file():
        raise MediaError(f"엔드카드 영상이 없습니다: {endcard_mp4}")

    main_info = probe(tools, final_mp4)
    end_info = probe(tools, endcard_mp4)
    if not main_info.has_video or main_info.duration <= 0.0:
        raise MediaError("최종 영상 정보가 유효하지 않습니다.")
    if not end_info.has_video or end_info.duration <= 0.0:
        raise MediaError("엔드카드 영상 정보가 유효하지 않습니다.")

    tmp_dir.mkdir(parents=True, exist_ok=True)
    joined_tmp = tmp_dir / "final_with_endcard.mp4"

    filters: List[str] = []
    if main_info.duration > 0.5:
        filters.append(fill_filter("0:v", "v0_base"))
        fade_st = max(0.0, main_info.duration - 0.20)
        filters.append(f"[v0_base]fade=t=out:st={fade_st:.3f}:d=0.20[v0]")
    else:
        filters.append(fill_filter("0:v", "v0"))
    filters.append(fill_filter("1:v", "v1"))

    for idx, info in ((0, main_info), (1, end_info)):
        if info.has_audio:
            filters.append(
                f"[{idx}:a]aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
                f"apad=whole_dur={info.duration:.3f},atrim=0:{info.duration:.3f}[a{idx}]"
            )
        else:
            filters.append(f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{info.duration:.3f}[a{idx}]")

    filters.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]")
    total = main_info.duration + end_info.duration
    run_ffmpeg(
        tools,
        [
            "-i", str(final_mp4),
            "-i", str(endcard_mp4),
            "-filter_complex", ";".join(filters),
            "-map", "[vout]",
            "-map", "[aout]",
            *VIDEO_ENCODE_ARGS,
            *AUDIO_ENCODE_ARGS,
            "-t", f"{total:.3f}",
            str(joined_tmp),
        ],
    )
    if not joined_tmp.is_file() or joined_tmp.stat().st_size <= 0:
        raise MediaError("엔드카드 합치기 출력 파일이 비어 있습니다.")

    try:
        os.replace(joined_tmp, final_mp4)
    except OSError:
        shutil.move(str(joined_tmp), str(final_mp4))
    return float(probe(tools, final_mp4).duration)
