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

FIGMA_VARIANTS = ("invert-box", "white-label", "serif-outline", "pov-bar")
_SSOT_CACHE: Optional[Dict[str, Any]] = None


def load_thumbnail_ssot() -> Dict[str, Any]:
    global _SSOT_CACHE
    if _SSOT_CACHE is None:
        ssot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbnail_ssot.json")
        if os.path.isfile(ssot_path):
            with open(ssot_path, "r", encoding="utf-8") as fh:
                _SSOT_CACHE = json.load(fh)
        else:
            _SSOT_CACHE = {}
    return _SSOT_CACHE


def _hex_to_rgb(val: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    s = str(val or "").strip().lstrip("#")
    if len(s) == 6:
        try:
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except ValueError:
            pass
    return default


def resolve_serif_font_path(font_override: Optional[str] = None) -> str:
    ssot = load_thumbnail_ssot()
    serif_cfg = (ssot.get("fonts") or {}).get("serif") or {}
    candidates: List[str] = []
    if font_override:
        candidates.append(font_override)
    env_serif = os.environ.get(str(serif_cfg.get("env_override") or "SHORTFORM_FONT_SERIF"), "").strip()
    if env_serif:
        candidates.append(env_serif)
    for cand in serif_cfg.get("pillow_candidates") or []:
        candidates.append(os.path.expanduser(str(cand)))
    candidates.extend([
        os.path.expanduser("~/Library/Fonts/BookkMyungjo-Bd.ttf"),
        os.path.expanduser("~/Library/Fonts/BookkMyungjo-Bd.otf"),
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/truetype/nanum/NanumMyeongjoBold.ttf",
        "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
    ])
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return resolve_font_path(font_override)


def compute_serif_outline_base_size(lines: Sequence[str], ssot: Dict[str, Any]) -> int:
    max_chars = max((len(str(ln).strip()) for ln in lines), default=1)
    rules = ((ssot.get("variants") or {}).get("serif-outline") or {}).get("dynamic_font_size") or [
        {"max_chars": 5, "font_size": 210},
        {"max_chars": 8, "font_size": 152},
        {"max_chars": None, "font_size": 112},
    ]
    for rule in rules:
        mc = rule.get("max_chars")
        if mc is None or max_chars <= int(mc):
            return int(rule["font_size"])
    return 112


def _split_highlight_segments(line: str, highlight_word: Optional[str]) -> List[Tuple[str, bool]]:
    target = str(highlight_word or "").strip()
    if target and target in line:
        idx = line.index(target)
        out: List[Tuple[str, bool]] = []
        if idx > 0:
            out.append((line[:idx], False))
        out.append((target, True))
        after = line[idx + len(target):]
        if after:
            out.append((after, False))
        return out
    return [(line, False)]


def _fit_figma_font_size(
    draw: ImageDraw.ImageDraw,
    lines: Sequence[str],
    *,
    font_path: str,
    base_size: int,
    min_size: int,
    max_width: int,
    stroke_width: int = 0,
    extra_pad_x: int = 0,
    max_total_height: Optional[int] = None,
    line_height_ratio: float = 1.2,
) -> int:
    eff = max(min_size, int(base_size))
    while eff > min_size:
        font = load_font(eff, font_path)
        widest = 0.0
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=font, stroke_width=stroke_width)
            w = max(float(bb[2] - bb[0]), float(draw.textlength(ln, font=font)) + stroke_width * 2)
            widest = max(widest, w + extra_pad_x)
        total_h = len(lines) * int(round(eff * line_height_ratio))
        height_ok = max_total_height is None or total_h <= max_total_height
        if widest <= max_width and height_ok:
            break
        if widest > max_width:
            scaled = int(eff * (max_width / max(widest, 1.0)))
            eff = max(min_size, min(eff - 2, scaled))
        else:
            eff = max(min_size, eff - 2)
    return eff


def _validate_figma_box(
    warnings: List[str],
    name: str,
    box: Tuple[int, int, int, int],
    ssot: Dict[str, Any],
) -> None:
    sz = ssot.get("safe_zone") or {}
    reels = sz.get("reels_ui") or {}
    ig34 = sz.get("ig_profile_3_4_crop") or {}
    cutout = reels.get("lower_right_cutout") or {}
    x_min = int(reels.get("x_min", 63))
    x_max = int(reels.get("x_max", 1016))
    y_min = int(ig34.get("y_min", 240))
    y_max = int(reels.get("y_max", 1396))
    cut_y = int(cutout.get("y_min", 1094))
    cut_x = int(cutout.get("x_max", 924))

    x0, y0, x1, y1 = box
    if y0 < y_min or y1 > y_max:
        warnings.append(f"{name} y=[{y0}, {y1}] exceeds Figma safe zone [{y_min}, {y_max}]")
    if x0 < x_min or x1 > x_max:
        warnings.append(f"{name} x=[{x0}, {x1}] exceeds Figma horizontal safe margin [{x_min}, {x_max}]")
    if y1 > cut_y and x1 > cut_x:
        warnings.append(f"{name} enters Reels lower-right cutout (x={x1} > {cut_x} at y={y1} > {cut_y})")


def _draw_figma_badge_pill(
    draw: ImageDraw.ImageDraw,
    *,
    center_x: Optional[int],
    left_x: int,
    top_y: int,
    text: str,
    font_path: str,
) -> Tuple[int, Tuple[int, int, int, int]]:
    font = load_font(28, font_path)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad_x = 26
    h = 56
    w = tw + pad_x * 2
    bx = (center_x - w // 2) if center_x is not None else left_x
    draw.rounded_rectangle([bx, top_y, bx + w, top_y + h], radius=h // 2, fill=(214, 255, 63, 255))
    tx = bx + pad_x - tb[0]
    ty = top_y + (h - th) // 2 - tb[1]
    draw.text((tx, ty), text, font=font, fill=(0, 0, 0, 255))
    return top_y + h + 18, (bx, top_y, bx + w, top_y + h)


def _draw_figma_line_segments(
    draw: ImageDraw.ImageDraw,
    *,
    line: str,
    start_x: int,
    font: ImageFont.ImageFont,
    base_rgb: Tuple[int, int, int],
    highlight_word: Optional[str],
    hi_rgb: Tuple[int, int, int],
    hi_bg_rgba: Optional[Tuple[int, int, int, int]] = None,
    stroke_rgba: Optional[Tuple[int, int, int, int]] = None,
    stroke_w: int = 0,
    hi_stroke_rgba: Optional[Tuple[int, int, int, int]] = None,
    box_center_y: Optional[int] = None,
    top_y: Optional[int] = None,
) -> Tuple[int, int, int, int]:
    full_bb = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)
    full_h = full_bb[3] - full_bb[1]
    if top_y is not None:
        anchor_y = top_y - full_bb[1]
    else:
        cy = int(box_center_y or 0)
        anchor_y = cy - full_h // 2 - full_bb[1]

    cur_x = float(start_x)
    min_x, max_x = start_x, start_x
    min_y, max_y = int(anchor_y + full_bb[1]), int(anchor_y + full_bb[3])
    for seg_text, is_hi in _split_highlight_segments(line, highlight_word):
        if not seg_text:
            continue
        seg_bb = draw.textbbox((0, 0), seg_text, font=font, stroke_width=stroke_w)
        seg_adv = float(draw.textlength(seg_text, font=font))
        seg_w = max(seg_adv, float(seg_bb[2] - seg_bb[0]))
        x_int = int(round(cur_x))
        if is_hi and hi_bg_rgba is not None:
            pad_h = 6
            pad_v = 4
            bx0 = x_int - pad_h
            by0 = int(anchor_y + seg_bb[1]) - pad_v
            bx1 = int(round(cur_x + seg_adv)) + pad_h
            by1 = int(anchor_y + seg_bb[3]) + pad_v
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=8, fill=hi_bg_rgba)
            min_x = min(min_x, bx0)
            max_x = max(max_x, bx1)
            min_y = min(min_y, by0)
            max_y = max(max_y, by1)
        sc = (hi_stroke_rgba or stroke_rgba) if is_hi else stroke_rgba
        fill_col = (*hi_rgb, 255) if is_hi else (*base_rgb, 255)
        if sc is not None and stroke_w > 0:
            draw.text(
                (x_int, anchor_y),
                seg_text,
                font=font,
                fill=fill_col,
                stroke_width=stroke_w,
                stroke_fill=sc,
            )
        else:
            draw.text((x_int, anchor_y), seg_text, font=font, fill=fill_col)
        min_x = min(min_x, x_int + seg_bb[0])
        max_x = max(max_x, int(round(cur_x + seg_w)) + stroke_w)
        cur_x += seg_adv
    return min_x, min_y, max_x, max_y


def _render_figma_thumbnail(
    item: Dict[str, Any],
    *,
    variant: str,
    base_dir: str,
    out_dir: str,
    font_path: str,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
) -> Dict[str, Any]:
    """Render one of the 4 canonical Storybook Figma cover styles using `thumbnail_ssot.json`."""
    ssot = load_thumbnail_ssot()
    vcfg = (ssot.get("variants") or {}).get(variant) or {}
    tid = item["id"]
    filename = item.get("filename") or f"thumb_{tid}.png"

    headline_cfg = item.get("headline") or {}
    raw_lines = headline_cfg.get("lines") or item.get("headline_lines") or []
    lines: List[str] = []
    for idx, ln in enumerate(raw_lines):
        txt = str(ln["text"] if isinstance(ln, dict) else (ln[0] if isinstance(ln, (list, tuple)) else ln)).strip()
        if txt:
            _check_no_emoji(txt, f"{tid}.headline.lines[{idx}]")
            lines.append(txt)
    badge_raw = item.get("badge")
    if badge_raw is None and isinstance(item.get("pill"), dict):
        badge_raw = item["pill"].get("text")
    badge_text = str(badge_raw or "").strip()
    if badge_text:
        _check_no_emoji(badge_text, f"{tid}.badge")
    highlight_word = str(item.get("highlight_word") or headline_cfg.get("highlight_word") or "").strip() or None
    if highlight_word:
        _check_no_emoji(highlight_word, f"{tid}.highlight_word")

    p_path = _resolve_path(base_dir, item["image"])
    with Image.open(p_path) as raw:
        cropped = _crop_source_image(raw, item)
        anchor = tuple(float(v) for v in item.get("anchor", (0.5, 0.5)))

    bg_rgb = _hex_to_rgb(vcfg.get("bg_fallback_hex", "#111317"), (17, 19, 23))
    bounds: Dict[str, List[int]] = {}
    warnings: List[str] = []

    if variant == "pov-bar":
        top_bar = vcfg.get("top_bar") or {}
        bar_h = int(top_bar.get("height", 560))
        text_y_min = int(top_bar.get("text_y_min", 248))
        text_y_max = int(top_bar.get("text_y_max", 532))
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        fitted_bottom = fit_cover(cropped, (width, height - bar_h), anchor=anchor, contrast=1.0).convert("RGBA")
        canvas.paste(fitted_bottom, (0, bar_h))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([0, 0, width, bar_h], fill=(0, 0, 0, 255))

        max_w = int(vcfg.get("max_text_width", 936))
        base_fs = int(vcfg.get("font_size", 60))
        min_fs = int(vcfg.get("min_font_size", 28))
        lh_ratio = float(vcfg.get("line_height", 1.32))
        badge_h = 74 if badge_text else 0
        avail_h = max(60, (text_y_max - text_y_min) - badge_h)
        eff_fs = _fit_figma_font_size(
            draw,
            lines or [" "],
            font_path=font_path,
            base_size=base_fs,
            min_size=min_fs,
            max_width=max_w,
            max_total_height=avail_h,
            line_height_ratio=lh_ratio,
        )
        font = load_font(eff_fs, font_path)
        line_h = int(round(eff_fs * lh_ratio))
        block_h = badge_h + len(lines) * line_h
        cur_y = text_y_min + max(0, (text_y_max - text_y_min - block_h) // 2)

        if badge_text:
            cur_y, pb = _draw_figma_badge_pill(
                draw, center_x=width // 2, left_x=width // 2, top_y=cur_y, text=badge_text, font_path=font_path
            )
            bounds["pill"] = list(pb)
            _validate_figma_box(warnings, "pill", pb, ssot)

        if lines:
            hx0, hy0, hx1, hy1 = width, height, 0, 0
            ink_rgb = _hex_to_rgb(vcfg.get("ink", "#ffffff"), (255, 255, 255))
            hi_rgb = _hex_to_rgb(vcfg.get("highlight_ink", "#d6ff3f"), (214, 255, 63))
            for ln in lines:
                tw = int(round(draw.textlength(ln, font=font)))
                lb = _draw_figma_line_segments(
                    draw,
                    line=ln,
                    start_x=(width - tw) // 2,
                    font=font,
                    base_rgb=ink_rgb,
                    highlight_word=highlight_word,
                    hi_rgb=hi_rgb,
                    box_center_y=cur_y + line_h // 2,
                )
                hx0, hy0, hx1, hy1 = min(hx0, lb[0]), min(hy0, lb[1]), max(hx1, lb[2]), max(hy1, lb[3])
                cur_y += line_h
            bounds["headline"] = [hx0, hy0, hx1, hy1]
            _validate_figma_box(warnings, "headline", (hx0, hy0, hx1, hy1), ssot)

    elif variant == "invert-box":
        canvas = fit_cover(cropped, (width, height), anchor=anchor, contrast=1.0).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        cur_y = int(vcfg.get("top", 296))
        if badge_text:
            cur_y, pb = _draw_figma_badge_pill(
                draw, center_x=width // 2, left_x=width // 2, top_y=cur_y, text=badge_text, font_path=font_path
            )
            bounds["pill"] = list(pb)
            _validate_figma_box(warnings, "pill", pb, ssot)

        if lines:
            pad_x = int(vcfg.get("pad_x", 22))
            pad_y = int(vcfg.get("pad_y", 10))
            max_w = int(vcfg.get("max_text_width", 900))
            max_bw = int(vcfg.get("max_box_width", 952))
            eff_fs = _fit_figma_font_size(
                draw,
                lines,
                font_path=font_path,
                base_size=int(vcfg.get("font_size", 78)),
                min_size=int(vcfg.get("min_font_size", 28)),
                max_width=max_w,
                extra_pad_x=16 if highlight_word else 0,
            )
            font = load_font(eff_fs, font_path)
            lh_ratio = float(vcfg.get("line_height", 1.16))
            box_h = int(round(eff_fs * lh_ratio + 2 * pad_y))
            even_cfg = vcfg.get("even_line") or {}
            odd_cfg = vcfg.get("odd_line") or {}

            hx0, hy0, hx1, hy1 = width, cur_y, 0, cur_y
            for idx, ln in enumerate(lines):
                is_odd = idx % 2 == 1
                lcfg = odd_cfg if is_odd else even_cfg
                box_rgb = _hex_to_rgb(lcfg.get("bg", "#020202" if is_odd else "#ffffff"))
                ink_rgb = _hex_to_rgb(lcfg.get("ink", "#ffffff" if is_odd else "#111111"))
                hi_rgb = _hex_to_rgb(lcfg.get("highlight_ink", "#d6ff3f" if is_odd else "#000000"))
                hi_bg_hex = lcfg.get("highlight_bg")
                hi_bg_rgba = (*_hex_to_rgb(hi_bg_hex), 255) if hi_bg_hex else None

                tw = int(round(draw.textlength(ln, font=font)))
                bw = min(max_bw, tw + pad_x * 2)
                bx = (width - bw) // 2
                draw.rectangle([bx, cur_y, bx + bw, cur_y + box_h], fill=(*box_rgb, 255))
                _draw_figma_line_segments(
                    draw,
                    line=ln,
                    start_x=(width - tw) // 2,
                    font=font,
                    base_rgb=ink_rgb,
                    highlight_word=highlight_word,
                    hi_rgb=hi_rgb,
                    hi_bg_rgba=hi_bg_rgba,
                    box_center_y=cur_y + box_h // 2,
                )
                hx0 = min(hx0, bx)
                hx1 = max(hx1, bx + bw)
                cur_y += box_h
                hy1 = max(hy1, cur_y)
            bounds["headline"] = [hx0, hy0, hx1, hy1]
            _validate_figma_box(warnings, "headline", (hx0, hy0, hx1, hy1), ssot)

    elif variant == "white-label":
        canvas = fit_cover(cropped, (width, height), anchor=anchor, contrast=1.0).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        left_x = int(vcfg.get("left", 68))
        cur_y = int(vcfg.get("top", 340))
        if badge_text:
            cur_y, pb = _draw_figma_badge_pill(
                draw, center_x=None, left_x=left_x, top_y=cur_y, text=badge_text, font_path=font_path
            )
            bounds["pill"] = list(pb)
            _validate_figma_box(warnings, "pill", pb, ssot)

        if lines:
            pad_x = int(vcfg.get("pad_x", 20))
            pad_y = int(vcfg.get("pad_y", 10))
            max_w = int(vcfg.get("max_text_width", 880))
            max_bw = int(vcfg.get("max_box_width", 944))
            eff_fs = _fit_figma_font_size(
                draw,
                lines,
                font_path=font_path,
                base_size=int(vcfg.get("font_size", 92)),
                min_size=int(vcfg.get("min_font_size", 28)),
                max_width=max_w,
                extra_pad_x=16 if highlight_word else 0,
            )
            font = load_font(eff_fs, font_path)
            lh_ratio = float(vcfg.get("line_height", 1.12))
            box_h = int(round(eff_fs * lh_ratio + 2 * pad_y))
            lcfg = vcfg.get("line_style") or {}
            box_rgb = _hex_to_rgb(lcfg.get("bg", "#ffffff"), (255, 255, 255))
            ink_rgb = _hex_to_rgb(lcfg.get("ink", "#000000"), (0, 0, 0))
            hi_rgb = _hex_to_rgb(lcfg.get("highlight_ink", "#000000"), (0, 0, 0))
            hi_bg_rgba = (*_hex_to_rgb(lcfg.get("highlight_bg", "#d6ff3f"), (214, 255, 63)), 255)

            hx0, hy0, hx1, hy1 = left_x, cur_y, left_x, cur_y
            for ln in lines:
                tw = int(round(draw.textlength(ln, font=font)))
                bw = min(max_bw, tw + pad_x * 2)
                draw.rectangle([left_x, cur_y, left_x + bw, cur_y + box_h], fill=(*box_rgb, 255))
                _draw_figma_line_segments(
                    draw,
                    line=ln,
                    start_x=left_x + pad_x,
                    font=font,
                    base_rgb=ink_rgb,
                    highlight_word=highlight_word,
                    hi_rgb=hi_rgb,
                    hi_bg_rgba=hi_bg_rgba,
                    box_center_y=cur_y + box_h // 2,
                )
                hx1 = max(hx1, left_x + bw)
                cur_y += box_h
                hy1 = max(hy1, cur_y)
            bounds["headline"] = [hx0, hy0, hx1, hy1]
            _validate_figma_box(warnings, "headline", (hx0, hy0, hx1, hy1), ssot)

    else:
        # serif-outline
        canvas = fit_cover(cropped, (width, height), anchor=anchor, contrast=1.0).convert("RGBA")
        serif_font_path = resolve_serif_font_path()
        tmp_draw = ImageDraw.Draw(canvas)
        cur_y = int(vcfg.get("top", 248))
        max_w = int(vcfg.get("max_text_width", 920))

        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        td = ImageDraw.Draw(text_layer)

        if badge_text:
            bcfg = vcfg.get("badge") or {}
            b_stroke_w = int(bcfg.get("stroke_width_pillow", 5))
            b_fs = _fit_figma_font_size(
                tmp_draw,
                [badge_text],
                font_path=serif_font_path,
                base_size=int(bcfg.get("font_size", 52)),
                min_size=26,
                max_width=max_w,
                stroke_width=b_stroke_w,
            )
            b_font = load_font(b_fs, serif_font_path)
            b_bb = tmp_draw.textbbox((0, 0), badge_text, font=b_font, stroke_width=b_stroke_w)
            b_tw = b_bb[2] - b_bb[0]
            b_th = b_bb[3] - b_bb[1]
            bx = (width - b_tw) // 2 - b_bb[0]
            by = cur_y - b_bb[1]
            sd.text(
                (bx, by + 4),
                badge_text,
                font=b_font,
                fill=(0, 0, 0, 115),
                stroke_width=b_stroke_w,
                stroke_fill=(0, 0, 0, 115),
            )
            td.text(
                (bx, by),
                badge_text,
                font=b_font,
                fill=(*_hex_to_rgb(bcfg.get("ink", "#ffffff"), (255, 255, 255)), 255),
                stroke_width=b_stroke_w,
                stroke_fill=(*_hex_to_rgb(bcfg.get("stroke_color", "#000000"), (0, 0, 0)), 255),
            )
            pb = (bx + b_bb[0], cur_y, bx + b_bb[2], cur_y + b_th)
            bounds["pill"] = list(pb)
            _validate_figma_box(warnings, "pill", pb, ssot)
            cur_y += b_th + int(bcfg.get("gap_below", 16))

        if lines:
            stroke_w = int(vcfg.get("stroke_width_pillow", 11))
            base_fs = compute_serif_outline_base_size(lines, ssot)
            eff_fs = _fit_figma_font_size(
                tmp_draw,
                lines,
                font_path=serif_font_path,
                base_size=base_fs,
                min_size=int(vcfg.get("min_font_size", 32)),
                max_width=max_w,
                stroke_width=stroke_w,
            )
            font = load_font(eff_fs, serif_font_path)
            lh_ratio = float(vcfg.get("line_height", 1.06))
            ink_rgb = _hex_to_rgb(vcfg.get("ink", "#000000"), (0, 0, 0))
            stroke_rgba = (*_hex_to_rgb(vcfg.get("stroke_color", "#ffffff"), (255, 255, 255)), 255)
            hi_rgb = _hex_to_rgb(vcfg.get("highlight_ink", "#d6ff3f"), (214, 255, 63))
            hi_stroke_rgba = (*_hex_to_rgb(vcfg.get("highlight_stroke_color", "#000000"), (0, 0, 0)), 255)

            hx0, hy0, hx1, hy1 = width, cur_y, 0, cur_y
            for ln in lines:
                l_bb = tmp_draw.textbbox((0, 0), ln, font=font, stroke_width=stroke_w)
                l_adv = int(round(tmp_draw.textlength(ln, font=font)))
                l_th = l_bb[3] - l_bb[1]
                start_x = (width - l_adv) // 2
                anchor_y = cur_y - l_bb[1]
                sd.text(
                    (start_x, anchor_y + 8),
                    ln,
                    font=font,
                    fill=(0, 0, 0, 82),
                    stroke_width=stroke_w,
                    stroke_fill=(0, 0, 0, 82),
                )
                lb = _draw_figma_line_segments(
                    td,
                    line=ln,
                    start_x=start_x,
                    font=font,
                    base_rgb=ink_rgb,
                    highlight_word=highlight_word,
                    hi_rgb=hi_rgb,
                    stroke_rgba=stroke_rgba,
                    stroke_w=stroke_w,
                    hi_stroke_rgba=hi_stroke_rgba,
                    top_y=cur_y,
                )
                hx0, hy0 = min(hx0, lb[0]), min(hy0, lb[1])
                hx1, hy1 = max(hx1, lb[2]), max(hy1, lb[3])
                cur_y += max(int(round(eff_fs * lh_ratio)), l_th + 6)
            bounds["headline"] = [hx0, hy0, hx1, hy1]
            _validate_figma_box(warnings, "headline", (hx0, hy0, hx1, hy1), ssot)

        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
        canvas = Image.alpha_composite(canvas, shadow_layer)
        canvas = Image.alpha_composite(canvas, text_layer)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)
    canvas.convert("RGB").save(out_path, format="PNG")
    return {
        "id": tid,
        "path": os.path.abspath(out_path),
        "width": width,
        "height": height,
        "layout": f"figma:{variant}",
        "figma_variant": variant,
        "strict_margin": True,
        "bounds": bounds,
        "safe_zone_ok": len(warnings) == 0,
        "warnings": warnings,
    }

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
    env_bold = os.environ.get("SHORTFORM_FONT_BOLD", "").strip()
    if env_bold:
        candidates.append(env_bold)
    candidates.extend([
        os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
        "/Library/Fonts/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
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
    figma_variant = item.get("figma_variant")
    if not figma_variant and isinstance(item.get("headline"), dict):
        cand_style = str(item["headline"].get("style") or "").strip().lower()
        if cand_style in FIGMA_VARIANTS:
            figma_variant = cand_style
    if figma_variant and str(figma_variant).strip().lower() in FIGMA_VARIANTS:
        return _render_figma_thumbnail(
            item,
            variant=str(figma_variant).strip().lower(),
            base_dir=base_dir,
            out_dir=out_dir,
            font_path=font_path,
            width=width,
            height=height,
        )
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
