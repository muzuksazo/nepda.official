#!/usr/bin/env python3
"""Programmatic source-video analyzer & keyframe contact-sheet builder for ad remixing.

Extracts ffprobe stream metadata, scene-cut timestamps, heuristic burned-in subtitle
warnings, a single labeled contact sheet for 1-turn LLM inspection, editorial 4-cut
strips, and individual bridge PNG frames for Google Flow Frames-to-Video.
Uses only Python stdlib + PIL + numpy + ffmpeg/ffprobe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        os.environ.get("SHORTFORM_FONT_BOLD", "").strip(),
        os.path.expanduser("~/Library/Fonts/NotoSansCJKkr-Bold.otf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def ffprobe_metadata(video_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of",
        "json",
        video_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    raw = json.loads(proc.stdout)
    fmt = raw.get("format", {})
    streams = raw.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    num, den = (v_stream.get("r_frame_rate") or "30/1").split("/")
    fps = round(float(num) / max(float(den), 1.0), 3)
    w = int(v_stream.get("width", 0) or 0)
    h = int(v_stream.get("height", 0) or 0)
    aspect = round(w / max(h, 1), 4)
    if abs(aspect - 1.0) < 0.08:
        aspect_label = "1:1"
        rec_framing = "blur-bleed"
    elif aspect < 0.72:
        aspect_label = "9:16"
        rec_framing = "full-bleed"
    elif 0.72 <= aspect <= 0.92:
        aspect_label = f"{w}:{h}"
        rec_framing = "smart-crop"
    elif aspect > 1.45:
        aspect_label = "16:9"
        rec_framing = "blur-bleed"
    else:
        aspect_label = f"{w}:{h}"
        rec_framing = "blur-bleed"

    return {
        "file": os.path.abspath(video_path),
        "duration": round(float(fmt.get("duration", 0.0) or 0.0), 3),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "bit_rate": int(fmt.get("bit_rate", 0) or 0),
        "width": w,
        "height": h,
        "fps": fps,
        "aspect_ratio": aspect,
        "aspect_label": aspect_label,
        "recommended_framing": rec_framing,
        "video_codec": v_stream.get("codec_name", ""),
        "has_audio": a_stream is not None,
        "audio_codec": a_stream.get("codec_name", "") if a_stream else None,
        "audio_sample_rate": int(a_stream.get("sample_rate", 0) or 0) if a_stream else 0,
        "audio_channels": int(a_stream.get("channels", 0) or 0) if a_stream else 0,
    }


def detect_scene_cuts(video_path: str, thresh: float = 0.28) -> List[float]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        video_path,
        "-vf",
        f"select='gt(scene,{thresh})',showinfo",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = proc.stderr or ""
    cuts: List[float] = []
    for m in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", text):
        ts = round(float(m.group(1)), 2)
        if not cuts or abs(ts - cuts[-1]) >= 0.25:
            cuts.append(ts)
    return cuts


def _extract_single_frame(video_path: str, ts: float, out_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{max(0.0, ts):.3f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            out_path,
        ],
        check=True,
    )


def _estimate_burned_in_subtitles(frame_paths: List[str]) -> Dict[str, Any]:
    """Heuristic check for high-contrast horizontal text bands near bottom 18% of frames."""
    if not frame_paths:
        return {"likely_burned_in_subtitles": False, "bottom_edge_score": 0.0, "suggested_bottom_crop_px": 0}
    scores: List[float] = []
    img_h = 1080
    for fp in frame_paths:
        with Image.open(fp) as im:
            rgb = im.convert("L")
            arr = np.asarray(rgb, dtype=np.float32)
            img_h = arr.shape[0]
            y0 = int(arr.shape[0] * 0.80)
            y1 = int(arr.shape[0] * 0.96)
            band = arr[y0:y1, :]
            if band.size == 0:
                continue
            dx = np.abs(np.diff(band, axis=1))
            dy = np.abs(np.diff(band, axis=0))
            strong_edges = float(np.mean(dx > 38.0) + np.mean(dy > 38.0)) * 0.5
            scores.append(strong_edges)
    mean_score = round(float(np.mean(scores)) if scores else 0.0, 4)
    likely = mean_score >= 0.018
    suggested_crop = int(round(img_h * 0.141)) if likely else 0
    return {
        "likely_burned_in_subtitles": likely,
        "bottom_edge_score": mean_score,
        "suggested_bottom_crop_px": suggested_crop,
    }


def _fmt_tc(sec: float) -> str:
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:04.1f}"


def cmd_analyze(args: argparse.Namespace) -> None:
    meta = ffprobe_metadata(args.input)
    dur = meta["duration"]
    os.makedirs(args.out_dir, exist_ok=True)

    cuts = detect_scene_cuts(args.input, thresh=args.scene_thresh)
    timestamps: List[float] = [0.2] if dur > 0.4 else [0.0]
    t = args.interval
    while t < max(dur - 0.12, 0.2):
        timestamps.append(round(t, 2))
        t += args.interval
    if dur > 0.5 and (not timestamps or dur - timestamps[-1] > 0.35):
        timestamps.append(round(max(0.0, dur - 0.25), 2))

    # Merge any scene cut timestamps that are far from existing samples
    tagged_samples: List[Tuple[float, bool]] = []
    for ts in timestamps:
        is_cut = any(abs(ts - c) <= 0.35 for c in cuts)
        tagged_samples.append((ts, is_cut))

    tmp_dir = tempfile.mkdtemp(prefix="ad_src_")
    try:
        frame_items: List[Tuple[float, bool, str]] = []
        for idx, (ts, is_cut) in enumerate(tagged_samples):
            fp = os.path.join(tmp_dir, f"f_{idx:03d}.png")
            _extract_single_frame(args.input, ts, fp)
            frame_items.append((ts, is_cut, fp))

        sub_est = _estimate_burned_in_subtitles([fp for _, _, fp in frame_items[::max(1, len(frame_items) // 10)]])

        cols = max(2, args.cols)
        tile_w = args.tile_w
        with Image.open(frame_items[0][2]) as im0:
            sw, sh = im0.size
        tile_h = int(round(tile_w * sh / max(sw, 1)))
        pad = 10
        hdr_h = 26
        top_bar = 44
        rows = (len(frame_items) + cols - 1) // cols
        canvas_w = pad + cols * (tile_w + pad)
        canvas_h = top_bar + pad + rows * (tile_h + hdr_h + pad)

        canvas = Image.new("RGB", (canvas_w, canvas_h), (20, 22, 28))
        draw = ImageDraw.Draw(canvas)
        f_title = _load_font(17)
        f_lbl = _load_font(13)

        hdr = (
            f"{os.path.basename(args.input)}  |  {meta['width']}x{meta['height']} ({meta['aspect_label']})  |  "
            f"{dur:.2f}s  |  {meta['fps']}fps  |  cuts={len(cuts)}  |  "
            f"sub_warn={'YES' if sub_est['likely_burned_in_subtitles'] else 'no'}"
        )
        draw.text((pad, 12), hdr, fill=(244, 246, 250), font=f_title)

        for idx, (ts, is_cut, fp) in enumerate(frame_items):
            r = idx // cols
            c = idx % cols
            x0 = pad + c * (tile_w + pad)
            y0 = top_bar + pad + r * (tile_h + hdr_h + pad)
            bg = (122, 34, 20) if is_cut else (38, 42, 52)
            draw.rectangle([x0, y0, x0 + tile_w, y0 + hdr_h + tile_h], fill=(30, 34, 42), outline=(68, 74, 90), width=1)
            draw.rectangle([x0, y0, x0 + tile_w, y0 + hdr_h], fill=bg)
            lbl = f"{_fmt_tc(ts)} ({ts:.1f}s)" + (" [CUT]" if is_cut else "")
            draw.text((x0 + 6, y0 + 5), lbl, fill=(250, 250, 252), font=f_lbl)
            with Image.open(fp) as im:
                fitted = ImageOps.contain(im.convert("RGB"), (tile_w, tile_h))
                canvas.paste(fitted, (x0 + (tile_w - fitted.width) // 2, y0 + hdr_h + (tile_h - fitted.height) // 2))

        sheet_path = os.path.join(args.out_dir, "source_contact_sheet.jpg")
        canvas.save(sheet_path, format="JPEG", quality=86)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    meta["scene_cuts_sec"] = cuts
    meta["sample_count"] = len(tagged_samples)
    meta.update(sub_est)
    meta["contact_sheet"] = sheet_path

    meta_path = os.path.join(args.out_dir, "source_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(
        json.dumps(
            {
                "metadata": meta_path,
                "contact_sheet": sheet_path,
                "duration": dur,
                "resolution": f"{meta['width']}x{meta['height']}",
                "aspect": meta["aspect_label"],
                "recommended_framing": meta["recommended_framing"],
                "scene_cuts": len(cuts),
                "likely_burned_in_subtitles": sub_est["likely_burned_in_subtitles"],
                "suggested_bottom_crop_px": sub_est["suggested_bottom_crop_px"],
            },
            ensure_ascii=False,
        )
    )


def cmd_extract_strip(args: argparse.Namespace) -> None:
    times = [float(x.strip()) for x in args.timestamps.split(",") if x.strip()]
    if not times:
        raise RuntimeError("--timestamps must contain at least one timestamp")
    labels = [x.strip() for x in args.labels.split(",")] if args.labels else []

    tmp_dir = tempfile.mkdtemp(prefix="ad_strip_")
    try:
        imgs: List[Tuple[float, str, Image.Image]] = []
        for idx, ts in enumerate(times):
            fp = os.path.join(tmp_dir, f"c_{idx}.png")
            _extract_single_frame(args.input, ts, fp)
            if args.save_frames_dir:
                os.makedirs(args.save_frames_dir, exist_ok=True)
                shutil.copyfile(fp, os.path.join(args.save_frames_dir, f"cut_{idx+1}_{ts:.1f}s.png"))
            with Image.open(fp) as im:
                lbl = labels[idx] if idx < len(labels) else _fmt_tc(ts)
                imgs.append((ts, lbl, im.convert("RGB")))

        gap = 8
        tw, th = args.tile_w, args.tile_h
        w_tot = len(imgs) * tw + max(0, len(imgs) - 1) * gap
        canvas = Image.new("RGB", (w_tot, th), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        f_tag = _load_font(18)

        for idx, (ts, lbl, im) in enumerate(imgs):
            fitted = ImageOps.fit(im, (tw, th), method=Image.Resampling.LANCZOS)
            x0 = idx * (tw + gap)
            canvas.paste(fitted, (x0, 0))
            if not args.no_labels:
                tag_txt = f"{lbl} ({_fmt_tc(ts)})" if labels else _fmt_tc(ts)
                bx0, by0 = x0 + 12, 12
                bbox = draw.textbbox((0, 0), tag_txt, font=f_tag)
                bw = (bbox[2] - bbox[0]) + 18
                bh = (bbox[3] - bbox[1]) + 12
                draw.rectangle([bx0, by0, bx0 + bw, by0 + bh], fill=(17, 19, 24))
                draw.text((bx0 + 9, by0 + 5), tag_txt, fill=(255, 255, 255), font=f_tag)

        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        canvas.save(args.out, format="JPEG", quality=90)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(json.dumps({"out": os.path.abspath(args.out), "cuts": len(times), "size": f"{w_tot}x{th}"}, ensure_ascii=False))


def cmd_extract_frame(args: argparse.Namespace) -> None:
    _extract_single_frame(args.input, args.time, args.out)
    with Image.open(args.out) as im:
        w, h = im.size
    print(json.dumps({"out": os.path.abspath(args.out), "time": args.time, "width": w, "height": h}, ensure_ascii=False))


def normalize_cfr(
    input_path: str,
    out_path: str,
    *,
    fps: int = 30,
    crf: int = 17,
) -> Dict[str, Any]:
    """Normalize raw phone footage (VFR/HEVC/.mov/extensionless) to CFR H.264 MP4 + 48kHz stereo AAC."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        input_path,
        "-r",
        str(int(fps)),
        "-c:v",
        "libx264",
        "-crf",
        str(int(crf)),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"normalize-cfr failed for {input_path}: {proc.stderr}")
    return ffprobe_metadata(out_path)


def cmd_normalize_cfr(args: argparse.Namespace) -> None:
    meta = normalize_cfr(args.input, args.out, fps=args.fps, crf=args.crf)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="Analyze source product video & extract ad remix assets")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("analyze", help="Probe metadata, detect cuts, and stitch contact sheet")
    pa.add_argument("--input", required=True)
    pa.add_argument("--out-dir", required=True)
    pa.add_argument("--interval", type=float, default=1.0)
    pa.add_argument("--scene-thresh", type=float, default=0.28)
    pa.add_argument("--cols", type=int, default=6)
    pa.add_argument("--tile-w", type=int, default=260)

    ps = sub.add_parser("extract-strip", help="Extract horizontal editorial strip of selected timestamps")
    ps.add_argument("--input", required=True)
    ps.add_argument("--timestamps", required=True, help="Comma-separated seconds, e.g. 2.6,7.2,11.2,22.5")
    ps.add_argument("--labels", default=None, help="Comma-separated labels")
    ps.add_argument("--out", required=True)
    ps.add_argument("--tile-w", type=int, default=520)
    ps.add_argument("--tile-h", type=int, default=520)
    ps.add_argument("--save-frames-dir", default=None)
    ps.add_argument("--no-labels", action="store_true")

    pf = sub.add_parser("extract-frame", help="Extract single PNG keyframe at exact timestamp")
    pf.add_argument("--input", required=True)
    pf.add_argument("--time", type=float, required=True)
    pf.add_argument("--out", required=True)

    pn = sub.add_parser("normalize-cfr", help="Normalize raw VFR/HEVC/extensionless phone footage to CFR H.264 MP4")
    pn.add_argument("--input", required=True)
    pn.add_argument("--out", required=True)
    pn.add_argument("--fps", type=int, default=30)
    pn.add_argument("--crf", type=int, default=17)

    args = p.parse_args()
    if args.cmd == "analyze":
        cmd_analyze(args)
    elif args.cmd == "extract-strip":
        cmd_extract_strip(args)
    elif args.cmd == "extract-frame":
        cmd_extract_frame(args)
    elif args.cmd == "normalize-cfr":
        cmd_normalize_cfr(args)


if __name__ == "__main__":
    main()
