"""Part A: Concatenate T1-T5 5s demo clips into a unified 5-template Showcase Reel
and generate a 5x3 Master QA Verification Grid (no API calls required).
"""

from __future__ import annotations

import os
import subprocess
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/yun-yeowon/workspace/ad-studio/viral-3d-templates"
OUT_DIR = os.path.join(ROOT, "outputs")
SHOWCASE_MP4 = os.path.join(OUT_DIR, "all_5_templates_showcase.mp4")
MASTER_GRID_PNG = os.path.join(OUT_DIR, "qa_all_5_templates_grid.png")
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

CLIPS: List[Tuple[str, str, str, float, float]] = [
    ("T1", "T1. 투하 & 액티브 래그돌", "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/ragdoll_test/hq_active_ragdoll_vo.mp4", 0.0, 4.96),
    ("T2", "T2. 강풍 블래스트 & 뒤집힘", "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/jet_umbrella_final.mp4", 3.0, 5.00),
    ("T3", "T3. 500톤 유압프레스 파쇄", os.path.join(OUT_DIR, "T3_hydraulic_crush/T3_hydraulic_crush_final.mp4"), 0.0, 4.96),
    ("T4", "T4. 3단계 스케일 드롭", os.path.join(OUT_DIR, "T4_scale_drop/T4_scale_drop_final.mp4"), 0.0, 4.96),
    ("T5", "T5. 10단 지수 거대 도미노", os.path.join(OUT_DIR, "T5_chain_domino/T5_chain_domino_final.mp4"), 0.0, 4.96),
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for idx in (4, 3, 2, 0):
        try:
            return ImageFont.truetype(FONT_PATH, size=size, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()


def make_badge_png(label: str, out_path: str) -> None:
    im = Image.new("RGBA", (720, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = load_font(28)
    bbox = d.textbbox((0, 0), label, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 32, 16
    box_w = tw + pad_x * 2 + 24
    box_h = th + pad_y * 2
    x0 = (720 - box_w) // 2
    y0 = (96 - box_h) // 2
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=box_h // 2, fill=(10, 14, 22, 215), outline=(64, 212, 255, 220), width=3)
    dot_r = 7
    cx, cy = x0 + 26, y0 + box_h // 2
    d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(64, 220, 255, 255))
    d.text((cx + 18, y0 + (box_h - th) // 2 - 4), label, font=f, fill=(255, 255, 255, 255))
    im.save(out_path)


def build_showcase() -> None:
    tmp_dir = os.path.join(OUT_DIR, "_showcase_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    badge_paths: List[str] = []
    cmd: List[str] = ["ffmpeg", "-y"]

    for code, title, src, ss, dur in CLIPS:
        assert os.path.exists(src), f"Missing source clip: {src}"
        bpath = os.path.join(tmp_dir, f"badge_{code}.png")
        make_badge_png(title, bpath)
        badge_paths.append(bpath)
        if ss > 0.0:
            cmd += ["-ss", f"{ss:.2f}", "-t", f"{dur:.2f}", "-i", src]
        else:
            cmd += ["-i", src]

    for bpath in badge_paths:
        cmd += ["-loop", "1", "-i", bpath]

    n = len(CLIPS)
    filters: List[str] = []
    concat_inputs: List[str] = []
    for i in range(n):
        b_idx = n + i
        filters.append(
            f"[{i}:v]scale=720:1280,fps=30,format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v{i}_norm];"
            f"[{b_idx}:v]format=rgba[b{i}];"
            f"[v{i}_norm][b{i}]overlay=0:42:shortest=1,format=yuv420p[v{i}];"
            f"[{i}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_inputs.append(f"[v{i}][a{i}]")

    filters.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[vout][aout]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        SHOWCASE_MP4,
    ]
    subprocess.run(cmd, check=True)
    print(f"[showcase] Saved {SHOWCASE_MP4}", flush=True)

    # Build 5 rows x 3 cols (1080 x 3200) Master QA Verification Grid
    tile_w, tile_h = 360, 640
    canvas = Image.new("RGB", (tile_w * 3, tile_h * n), (12, 14, 18))
    draw = ImageDraw.Draw(canvas)
    f_row = load_font(22)
    for row_idx, (code, title, src, ss, dur) in enumerate(CLIPS):
        for col_idx, frac in enumerate((0.20, 0.55, 0.85)):
            t_sec = ss + dur * frac
            frame_png = os.path.join(tmp_dir, f"grid_{code}_{col_idx}.png")
            subprocess.run([
                "ffmpeg", "-y", "-ss", f"{t_sec:.2f}", "-i", src,
                "-frames:v", "1", "-q:v", "2", frame_png,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            im = Image.open(frame_png).convert("RGB").resize((tile_w, tile_h), Image.Resampling.LANCZOS)
            canvas.paste(im, (col_idx * tile_w, row_idx * tile_h))
        # Subtle row title pill on top-left of col 0
        ry = row_idx * tile_h + 12
        draw.rounded_rectangle([12, ry, 344, ry + 38], radius=8, fill=(10, 14, 22))
        draw.text((22, ry + 6), title, font=f_row, fill=(80, 230, 255))

    canvas.save(MASTER_GRID_PNG)
    print(f"[showcase] Saved {MASTER_GRID_PNG}", flush=True)


if __name__ == "__main__":
    build_showcase()
