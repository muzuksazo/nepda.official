#!/usr/bin/env python3
"""Programmatic 1080x1920 Reels/Shorts cover thumbnail & safe-zone QA sheet builder.

Clean-room CLI tool driven by a JSON specification (`--spec thumbs_spec.json`).
Renders crisp 1080x1920 cover PNGs (supporting `single` full-bleed covers,
`split_2panel` match-cut vertical splits, vertical gradient text scrims,
pill badges with optional indicator dots, oversized bold headlines in
`stroke_bold` / `line_blocks` / `panel_card` styles with horizontal auto-fit,
and rounded product inset cards). Validates both 1:1 (`y = 420..1500`) and
strict inner zero-clip margins (`y = 460..1460`, `x = 56..1024`, IG 3:4 `240..1680`).
Guide lines appear ONLY on the optional QA contact sheet.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

DEFAULT_W, DEFAULT_H = 1080, 1920
SAFE_Y_MIN = 420
SAFE_Y_MAX = 1500
STRICT_Y_MIN = 460
STRICT_Y_MAX = 1460
GRID_3_4_Y_MIN = 240
GRID_3_4_Y_MAX = 1680
SAFE_X_MIN = 56
SAFE_X_MAX = 1024

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def resolve_font_path(font_override: Optional[str] = None) -> str:
    candidates = []
    if font_override:
        candidates.append(font_override)
    candidates.extend([
        os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
        "/Library/Fonts/NotoSansCJKkr-Bold.otf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ])
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    raise FileNotFoundError("No usable bold CJK/Latin font found; pass --font explicitly")


def load_font(size: int, font_path: str) -> ImageFont.ImageFont:
    return ImageFont.truetype(font_path, size)


def _resolve_path(base_dir: str, rel_or_abs: str) -> str:
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.abspath(os.path.join(base_dir, rel_or_abs))


def _crop_source_image(im: Image.Image, cfg: Dict[str, Any]) -> Image.Image:
    im = im.convert("RGB")
    w, h = im.size
    if cfg.get("crop_px"):
        x0, y0, x1, y1 = [int(v) for v in cfg["crop_px"]]
        im = im.crop((max(0, x0), max(0, y0), min(w, x1), min(h, y1)))
    elif cfg.get("crop_norm"):
        nx0, ny0, nx1, ny1 = [float(v) for v in cfg["crop_norm"]]
        im = im.crop((
            max(0, int(round(w * nx0))),
            max(0, int(round(h * ny0))),
            min(w, int(round(w * nx1))),
            min(h, int(round(h * ny1))),
        ))
    return im


def fit_cover(
    im: Image.Image,
    target_size: Tuple[int, int],
    *,
    anchor: Tuple[float, float] = (0.5, 0.5),
    contrast: float = 1.06,
) -> Image.Image:
    fitted = ImageOps.fit(im.convert("RGB"), target_size, method=Image.Resampling.LANCZOS, centering=anchor)
    if abs(contrast - 1.0) > 1e-3:
        fitted = ImageEnhance.Contrast(fitted).enhance(contrast)
    return fitted


def add_band_scrim(
    canvas: Image.Image,
    y_top: int,
    y_bottom: int,
    *,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    peak_alpha: int = 195,
    edge_soft: int = 125,
    rgb: Tuple[int, int, int] = (8, 10, 16),
) -> Image.Image:
    """Apply smooth vertical gradient band strictly over text zone so imagery breathes elsewhere."""
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    alpha = np.zeros(height, dtype=np.float32)
    y0 = max(0, int(y_top) - int(edge_soft))
    y1 = max(0, min(height - 1, int(y_top)))
    y2 = max(y1, min(height - 1, int(y_bottom)))
    y3 = min(height - 1, int(y_bottom) + int(edge_soft))
    if y1 > y0:
        alpha[y0:y1] = np.linspace(0.0, float(peak_alpha), y1 - y0)
    alpha[y1:y2] = float(peak_alpha)
    if y3 > y2:
        alpha[y2:y3] = np.linspace(float(peak_alpha), 0.0, y3 - y2)
    arr[:, :, 0] = int(rgb[0])
    arr[:, :, 1] = int(rgb[1])
    arr[:, :, 2] = int(rgb[2])
    arr[:, :, 3] = alpha[:, None].astype(np.uint8)
    overlay = Image.fromarray(arr, mode="RGBA")
    return Image.alpha_composite(canvas.convert("RGBA"), overlay)


def draw_pill(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    top_y: int,
    text: str,
    *,
    font_path: str,
    fill: Tuple[int, int, int, int] = (214, 48, 34, 242),
    outline: Tuple[int, int, int, int] = (255, 255, 255, 110),
    dot_color: Optional[Tuple[int, int, int, int]] = None,
    font_size: int = 42,
    text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
) -> Tuple[int, int, int, int]:
    font = load_font(font_size, font_path)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad_x = 36
    dot_gap = 30 if dot_color else 0
    pw = tw + pad_x * 2 + dot_gap
    ph = th + 28
    x0 = center_x - pw // 2
    y0 = top_y
    draw.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph // 2, fill=fill, outline=outline, width=2)
    tx = x0 + pad_x + dot_gap
    ty = y0 + (ph - th) // 2 - tb[1]
    if dot_color:
        dy = y0 + ph // 2
        dx = x0 + pad_x + 4
        draw.ellipse([dx - 8, dy - 8, dx + 8, dy + 8], fill=dot_color)
    draw.text((tx, ty), text, font=font, fill=text_color)
    return x0, y0, x0 + pw, y0 + ph


HeadlineLineInput = Union[Tuple[str, Tuple[int, int, int]], Dict[str, Any]]


def _normalize_rgba(col: Sequence[int], default_alpha: int = 255) -> Tuple[int, int, int, int]:
    vals = [int(c) for c in col]
    if len(vals) >= 4:
        return vals[0], vals[1], vals[2], vals[3]
    return vals[0], vals[1], vals[2], default_alpha


def draw_headline(
    img: Image.Image,
    center_x: int,
    start_y: int,
    lines: List[HeadlineLineInput],
    *,
    font_path: str,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    font_size: int = 122,
    line_gap: int = 18,
    stroke_w: int = 11,
    style: str = "stroke_bold",
    block_fill: Tuple[int, int, int, int] = (255, 255, 255, 248),
    block_pad_x: int = 28,
    block_pad_y: int = 14,
    block_radius: int = 20,
    card_fill: Tuple[int, int, int, int] = (12, 14, 22, 228),
    card_outline: Optional[Tuple[int, int, int, int]] = (255, 255, 255, 65),
    card_pad_x: int = 40,
    card_pad_y: int = 28,
    card_radius: int = 32,
    max_text_width: Optional[int] = None,
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """Render oversized multi-line headline with horizontal auto-fit across 3 IG-proven styles."""
    if not lines:
        return img.convert("RGBA"), (center_x, start_y, center_x, start_y)

    norm_lines: List[Dict[str, Any]] = []
    for ln in lines:
        if isinstance(ln, dict):
            norm_lines.append({
                "text": str(ln["text"]),
                "color": tuple(int(c) for c in ln.get("color", (16, 20, 28) if style == "line_blocks" else (255, 255, 255)))[:3],
                "bg": _normalize_rgba(ln["bg"]) if ln.get("bg") else None,
            })
        else:
            norm_lines.append({
                "text": str(ln[0]),
                "color": tuple(int(c) for c in ln[1])[:3],
                "bg": None,
            })

    tmp_draw = ImageDraw.Draw(img)
    max_w = int(max_text_width if max_text_width is not None else max(320, width - 2 * SAFE_X_MIN))
    extra_w = (block_pad_x * 2) if style == "line_blocks" else ((card_pad_x * 2) if style == "panel_card" else (stroke_w * 2))

    eff_size = int(font_size)
    while eff_size > 48:
        font = load_font(eff_size, font_path)
        widest = 0
        for ln in norm_lines:
            tb = tmp_draw.textbbox((0, 0), ln["text"], font=font)
            widest = max(widest, (tb[2] - tb[0]) + extra_w)
        if widest <= max_w:
            break
        eff_size = max(48, min(eff_size - 4, int(eff_size * (max_w / float(max(widest, 1))))))

    font = load_font(eff_size, font_path)
    shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)

    y_cur = start_y
    if style == "panel_card":
        y_cur += card_pad_y

    positions: List[Dict[str, Any]] = []
    min_x, max_x = width, 0
    min_y, max_y = height, 0

    for ln in norm_lines:
        txt = ln["text"]
        col = ln["color"]
        tb = tmp_draw.textbbox((0, 0), txt, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]

        if style == "line_blocks":
            bx0 = center_x - tw // 2 - block_pad_x
            bx1 = bx0 + tw + block_pad_x * 2
            by0 = y_cur
            by1 = by0 + th + block_pad_y * 2
            tx = center_x - tw // 2 - tb[0]
            ty = by0 + block_pad_y - tb[1]
            bg = ln["bg"] or block_fill
            positions.append({"tx": tx, "ty": ty, "txt": txt, "col": col, "box": [bx0, by0, bx1, by1], "bg": bg})
            min_x = min(min_x, bx0)
            max_x = max(max_x, bx1)
            min_y = min(min_y, by0)
            max_y = max(max_y, by1)
            sd.rounded_rectangle(
                [bx0 + 2, by0 + 8, bx1 + 2, by1 + 8],
                radius=block_radius,
                fill=(0, 0, 0, 185),
            )
            y_cur = by1 + line_gap
        else:
            tx = center_x - tw // 2 - tb[0]
            raw_x0 = center_x - tw // 2
            ty = y_cur - tb[1]
            positions.append({"tx": tx, "ty": ty, "txt": txt, "col": col})
            min_x = min(min_x, raw_x0)
            max_x = max(max_x, raw_x0 + tw)
            min_y = min(min_y, y_cur)
            max_y = max(max_y, y_cur + th)
            if style != "panel_card":
                sd.text(
                    (tx + 2, ty + 8),
                    txt,
                    font=font,
                    fill=(0, 0, 0, 215),
                    stroke_width=stroke_w + 2,
                    stroke_fill=(0, 0, 0, 215),
                )
            y_cur += th + line_gap

    if style == "panel_card":
        cx0 = min_x - card_pad_x
        cx1 = max_x + card_pad_x
        cy0 = start_y
        cy1 = max_y + card_pad_y
        sd.rounded_rectangle([cx0 + 2, cy0 + 10, cx1 + 2, cy1 + 10], radius=card_radius, fill=(0, 0, 0, 195))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=14))
        out = Image.alpha_composite(img.convert("RGBA"), shadow_layer)
        card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card_layer)
        cd.rounded_rectangle(
            [cx0, cy0, cx1, cy1],
            radius=card_radius,
            fill=card_fill,
            outline=card_outline,
            width=2 if card_outline else 0,
        )
        out = Image.alpha_composite(out, card_layer)
        draw = ImageDraw.Draw(out)
        for p in positions:
            draw.text((p["tx"], p["ty"]), p["txt"], font=font, fill=(*p["col"], 255))
        return out, (cx0, cy0, cx1, cy1)

    if style == "line_blocks":
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=11))
        out = Image.alpha_composite(img.convert("RGBA"), shadow_layer)
        blk_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        bd = ImageDraw.Draw(blk_layer)
        for p in positions:
            bd.rounded_rectangle(p["box"], radius=block_radius, fill=p["bg"])
        out = Image.alpha_composite(out, blk_layer)
        draw = ImageDraw.Draw(out)
        for p in positions:
            draw.text((p["tx"], p["ty"]), p["txt"], font=font, fill=(*p["col"], 255))
        return out, (min_x, min_y, max_x, max_y)

    # Default: stroke_bold
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=9))
    out = Image.alpha_composite(img.convert("RGBA"), shadow_layer)
    draw = ImageDraw.Draw(out)
    for p in positions:
        draw.text(
            (p["tx"], p["ty"]),
            p["txt"],
            font=font,
            fill=(*p["col"], 255),
            stroke_width=stroke_w,
            stroke_fill=(10, 12, 16, 252),
        )
    return out, (min_x - stroke_w, min_y - stroke_w, max_x + stroke_w, max_y + stroke_w)


def paste_rounded_card(
    canvas: Image.Image,
    crop_img: Image.Image,
    box_xy: Tuple[int, int],
    *,
    size: int = 305,
    radius: int = 34,
    border: int = 8,
    shadow_alpha: int = 185,
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """Paste square product inset cleanly with crisp white border & drop shadow."""
    card = ImageOps.fit(crop_img.convert("RGB"), (size, size), method=Image.Resampling.LANCZOS)
    inner_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(inner_mask).rounded_rectangle([0, 0, size, size], radius=radius, fill=255)

    outer_s = size + border * 2
    frame = Image.new("RGBA", (outer_s, outer_s), (255, 255, 255, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle([0, 0, outer_s, outer_s], radius=radius + border // 2, fill=(255, 255, 255, 248))
    frame.paste(card, (border, border), inner_mask)

    sh_pad = 30
    sh = Image.new("RGBA", (outer_s + sh_pad * 2, outer_s + sh_pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [sh_pad, sh_pad + 8, sh_pad + outer_s, sh_pad + 8 + outer_s],
        radius=radius + border // 2,
        fill=(0, 0, 0, shadow_alpha),
    )
    sh = sh.filter(ImageFilter.GaussianBlur(radius=14))

    base = canvas.convert("RGBA")
    x, y = int(box_xy[0]), int(box_xy[1])
    base.paste(sh, (x - sh_pad, y - sh_pad), sh)
    base.paste(frame, (x, y), frame)
    return base, (x, y, x + outer_s, y + outer_s)


def _check_no_emoji(text: str, field_name: str) -> None:
    if EMOJI_RE.search(text or ""):
        raise ValueError(f"Emoji detected in {field_name}; cover thumbnails must remain emoji-free")


def _validate_element_box(
    warnings: List[str],
    name: str,
    box: Tuple[int, int, int, int],
    *,
    width: int,
    strict_margin: bool,
) -> None:
    x0, y0, x1, y1 = box
    y_min = STRICT_Y_MIN if strict_margin else SAFE_Y_MIN
    y_max = STRICT_Y_MAX if strict_margin else SAFE_Y_MAX
    x_min = SAFE_X_MIN if strict_margin else 44
    x_max = (width - SAFE_X_MIN) if strict_margin else (width - 44)
    label = "strict 1:1/3:4 safe zone" if strict_margin else "1:1 safe zone"
    if y0 < y_min or y1 > y_max:
        warnings.append(f"{name} y=[{y0}, {y1}] exceeds {label} [{y_min}, {y_max}]")
    if x0 < x_min or x1 > x_max:
        warnings.append(f"{name} x=[{x0}, {x1}] exceeds horizontal safe margin [{x_min}, {x_max}]")


def render_thumbnail(
    item: Dict[str, Any],
    *,
    base_dir: str,
    out_dir: str,
    font_path: str,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    default_strict_margin: bool = False,
) -> Dict[str, Any]:
    tid = item["id"]
    filename = item.get("filename") or f"thumb_{tid}.png"
    layout = item.get("layout", "single")
    strict_margin = bool(item.get("strict_margin", default_strict_margin))

    if layout == "split_2panel":
        panels = item.get("panels") or []
        if len(panels) != 2:
            raise ValueError(f"Thumbnail '{tid}' split_2panel requires exactly 2 panels")
        bg = tuple(int(c) for c in item.get("background", (16, 18, 24)))
        canvas = Image.new("RGBA", (width, height), (*bg[:3], 255))
        for idx, p in enumerate(panels):
            p_path = _resolve_path(base_dir, p["image"])
            with Image.open(p_path) as raw:
                cropped = _crop_source_image(raw, p)
                ph = int(p.get("height", height // 2))
                pw = int(p.get("width", width))
                px = int(p.get("x", 0))
                py = int(p.get("y", 0 if idx == 0 else height - ph))
                anchor = tuple(float(v) for v in p.get("anchor", (0.5, 0.5)))
                contrast = float(p.get("contrast", 1.06))
                fitted = fit_cover(cropped, (pw, ph), anchor=anchor, contrast=contrast)
                canvas.paste(fitted, (px, py))
    elif layout == "single":
        p_path = _resolve_path(base_dir, item["image"])
        with Image.open(p_path) as raw:
            cropped = _crop_source_image(raw, item)
            anchor = tuple(float(v) for v in item.get("anchor", (0.5, 0.5)))
            contrast = float(item.get("contrast", 1.06))
            canvas = fit_cover(cropped, (width, height), anchor=anchor, contrast=contrast).convert("RGBA")
    else:
        raise ValueError(f"Unsupported thumbnail layout '{layout}' for '{tid}'")

    scrim = item.get("scrim")
    if scrim:
        canvas = add_band_scrim(
            canvas,
            int(scrim["y_top"]),
            int(scrim["y_bottom"]),
            width=width,
            height=height,
            peak_alpha=int(scrim.get("peak_alpha", 195)),
            edge_soft=int(scrim.get("edge_soft", 125)),
            rgb=tuple(int(c) for c in scrim.get("rgb", (8, 10, 16)))[:3],
        )

    bounds: Dict[str, List[int]] = {}
    warnings: List[str] = []
    next_y = None

    pill = item.get("pill")
    if pill:
        ptxt = str(pill["text"])
        _check_no_emoji(ptxt, f"{tid}.pill.text")
        fill = _normalize_rgba(pill.get("fill", (214, 48, 34, 242)))
        outline = _normalize_rgba(pill.get("outline", (255, 255, 255, 110)))
        dc_raw = pill.get("dot_color")
        dot_col = _normalize_rgba(dc_raw) if dc_raw else None
        tcol = _normalize_rgba(pill.get("text_color", (255, 255, 255, 255)))
        draw = ImageDraw.Draw(canvas)
        pb = draw_pill(
            draw,
            int(pill.get("center_x", width // 2)),
            int(pill["y"]),
            ptxt,
            font_path=font_path,
            fill=fill,
            outline=outline,
            dot_color=dot_col,
            font_size=int(pill.get("font_size", 42)),
            text_color=tcol,
        )
        bounds["pill"] = list(pb)
        next_y = pb[3]
        _validate_element_box(warnings, "pill", pb, width=width, strict_margin=strict_margin)

    headline = item.get("headline")
    if headline:
        raw_lines = headline.get("lines") or []
        h_style = str(headline.get("style", "stroke_bold"))
        parsed_lines: List[HeadlineLineInput] = []
        for idx, ln in enumerate(raw_lines):
            if isinstance(ln, dict):
                ltxt = str(ln["text"])
                _check_no_emoji(ltxt, f"{tid}.headline.lines[{idx}]")
                parsed_lines.append(ln)
            else:
                ltxt = str(ln[0])
                _check_no_emoji(ltxt, f"{tid}.headline.lines[{idx}]")
                parsed_lines.append((ltxt, tuple(int(c) for c in ln[1])[:3]))
        start_y = int(
            headline["y"]
            if "y" in headline
            else ((next_y or (STRICT_Y_MIN if strict_margin else SAFE_Y_MIN)) + int(headline.get("gap_after_pill", 22)))
        )
        card_out_raw = headline.get("card_outline")
        canvas, hb = draw_headline(
            canvas,
            int(headline.get("center_x", width // 2)),
            start_y,
            parsed_lines,
            font_path=font_path,
            width=width,
            height=height,
            font_size=int(headline.get("font_size", 122)),
            line_gap=int(headline.get("line_gap", 18)),
            stroke_w=int(headline.get("stroke_w", 11)),
            style=h_style,
            block_fill=_normalize_rgba(headline.get("block_fill", (255, 255, 255, 248))),
            block_pad_x=int(headline.get("block_pad_x", 28)),
            block_pad_y=int(headline.get("block_pad_y", 14)),
            block_radius=int(headline.get("block_radius", 20)),
            card_fill=_normalize_rgba(headline.get("card_fill", (12, 14, 22, 228))),
            card_outline=_normalize_rgba(card_out_raw) if card_out_raw is not None else (255, 255, 255, 65),
            card_pad_x=int(headline.get("card_pad_x", 40)),
            card_pad_y=int(headline.get("card_pad_y", 28)),
            card_radius=int(headline.get("card_radius", 32)),
            max_text_width=int(headline["max_text_width"]) if "max_text_width" in headline else None,
        )
        bounds["headline"] = list(hb)
        _validate_element_box(warnings, "headline", hb, width=width, strict_margin=strict_margin)

    for idx, card in enumerate(item.get("inset_cards") or []):
        c_path = _resolve_path(base_dir, card["image"])
        with Image.open(c_path) as raw_card:
            cropped_card = _crop_source_image(raw_card, card)
            canvas, cb = paste_rounded_card(
                canvas,
                cropped_card,
                (int(card["x"]), int(card["y"])),
                size=int(card.get("size", 305)),
                radius=int(card.get("radius", 34)),
                border=int(card.get("border", 8)),
                shadow_alpha=int(card.get("shadow_alpha", 185)),
            )
        bounds[f"inset_card_{idx}"] = list(cb)
        _validate_element_box(warnings, f"inset_card[{idx}]", cb, width=width, strict_margin=strict_margin)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)
    canvas.convert("RGB").save(out_path, format="PNG")
    return {
        "id": tid,
        "path": os.path.abspath(out_path),
        "width": width,
        "height": height,
        "layout": layout,
        "strict_margin": strict_margin,
        "bounds": bounds,
        "safe_zone_ok": len(warnings) == 0,
        "warnings": warnings,
    }


def build_contact_sheet(
    rendered: List[Dict[str, Any]],
    sheet_path: str,
    *,
    font_path: str,
    canvas_width: int = DEFAULT_W,
    canvas_height: int = DEFAULT_H,
    tile_w: int = 360,
    tile_h: int = 640,
) -> str:
    pad, hdr = 18, 42
    sw = pad + len(rendered) * (tile_w + pad)
    sh = pad * 2 + hdr + tile_h
    sheet = Image.new("RGB", (sw, sh), (20, 23, 30))
    sdraw = ImageDraw.Draw(sheet)
    f_hdr = load_font(20, font_path)
    y_11_top = int(round(SAFE_Y_MIN / canvas_height * tile_h))
    y_11_bot = int(round(SAFE_Y_MAX / canvas_height * tile_h))
    y_34_top = int(round(GRID_3_4_Y_MIN / canvas_height * tile_h))
    y_34_bot = int(round(GRID_3_4_Y_MAX / canvas_height * tile_h))
    x_left = int(round(SAFE_X_MIN / canvas_width * tile_w))
    x_right = int(round((canvas_width - SAFE_X_MIN) / canvas_width * tile_w))

    for idx, info in enumerate(rendered):
        x0 = pad + idx * (tile_w + pad)
        y0 = pad + hdr
        sdraw.rectangle([x0, pad, x0 + tile_w, pad + hdr], fill=(40, 46, 58))
        lbl = f"{info['id']}" if info["safe_zone_ok"] else f"{info['id']} [WARN]"
        sdraw.text((x0 + 12, pad + 8), lbl, font=f_hdr, fill=(240, 244, 250))
        with Image.open(info["path"]) as im:
            tile = im.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
        sheet.paste(tile, (x0, y0))
        # Amber dashed lines: 3:4 IG profile-grid crop (y=240..1680)
        for gy in (y0 + y_34_top, y0 + y_34_bot):
            for dx in range(0, tile_w, 16):
                sdraw.line([(x0 + dx, gy), (x0 + min(tile_w, dx + 7), gy)], fill=(255, 195, 65), width=2)
        # Cyan dashed lines: 1:1 profile-grid center crop (y=420..1500)
        for gy in (y0 + y_11_top, y0 + y_11_bot):
            for dx in range(0, tile_w, 14):
                sdraw.line([(x0 + dx, gy), (x0 + min(tile_w, dx + 8), gy)], fill=(0, 225, 255), width=2)
        # Side margin guides (x=56..1024)
        for gx in (x0 + x_left, x0 + x_right):
            for dy in range(y_11_top, y_11_bot, 18):
                sdraw.line([(gx, y0 + dy), (gx, y0 + min(y_11_bot, dy + 8))], fill=(120, 240, 175), width=1)

    os.makedirs(os.path.dirname(os.path.abspath(sheet_path)), exist_ok=True)
    sheet.save(sheet_path, format="PNG")
    return os.path.abspath(sheet_path)


def build_from_spec(
    spec_path: str,
    out_dir: str,
    *,
    sheet_path: Optional[str] = None,
    font_override: Optional[str] = None,
) -> Dict[str, Any]:
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    base_dir = os.path.dirname(os.path.abspath(spec_path))
    canvas_cfg = spec.get("canvas") or {}
    width = int(canvas_cfg.get("width", DEFAULT_W))
    height = int(canvas_cfg.get("height", DEFAULT_H))
    font_path = resolve_font_path(font_override or spec.get("font"))
    default_strict = bool(spec.get("strict_margin", False))

    thumbs = spec.get("thumbnails") or []
    if not thumbs:
        raise ValueError("Specification must contain at least one entry in 'thumbnails'")

    rendered: List[Dict[str, Any]] = []
    for item in thumbs:
        rendered.append(
            render_thumbnail(
                item,
                base_dir=base_dir,
                out_dir=out_dir,
                font_path=font_path,
                width=width,
                height=height,
                default_strict_margin=default_strict,
            )
        )

    out_sheet = None
    if sheet_path:
        out_sheet = build_contact_sheet(
            rendered,
            sheet_path,
            font_path=font_path,
            canvas_width=width,
            canvas_height=height,
        )

    return {
        "out_dir": os.path.abspath(out_dir),
        "sheet": out_sheet,
        "count": len(rendered),
        "all_safe_zone_ok": all(r["safe_zone_ok"] for r in rendered),
        "thumbnails": rendered,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Build 1080x1920 Reels/Shorts cover thumbnails + safe-zone QA sheet")
    p.add_argument("--spec", required=True, help="JSON spec describing cover thumbnails")
    p.add_argument("--out-dir", required=True, help="Output directory for cover PNGs")
    p.add_argument("--sheet", default=None, help="Optional QA contact sheet PNG path (with 1:1 / 3:4 safe-zone guides)")
    p.add_argument("--font", default=None, help="Optional path to bold CJK/Latin font file")
    args = p.parse_args()

    res = build_from_spec(args.spec, args.out_dir, sheet_path=args.sheet, font_override=args.font)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
