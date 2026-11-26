#!/usr/bin/env python3
"""Unified CLI Runner for the 5-Archetype Blender 5.1 Viral 3D Physics Templates.

Usage:
  # 4-frame Visual Gate preview only:
  python3 run_template.py --spec specs/T3_hydraulic_crush.json --preview-only --samples 24

  # Full 150-frame render + encode + Inworld VO + SFX + PIL captions:
  INWORLD_AUTH=... python3 run_template.py --spec specs/T3_hydraulic_crush.json --render-all --assemble --samples 24
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = "/Users/yun-yeowon/workspace/ad-studio/viral-3d-templates"
BLENDER_BIN = "/opt/homebrew/bin/blender"
FFMPEG_BIN = "/opt/homebrew/bin/ffmpeg"

sys.path.insert(0, ROOT)


def _inside_blender() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def _blender_main() -> None:
    import bpy
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    args = p.parse_args(argv)

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    tid = spec["template"]
    out_dir = os.path.join(ROOT, "outputs", spec["id"])
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    blend_path = os.path.join(out_dir, f"{spec['id']}.blend")

    if tid == "T1_drop_launch":
        from templates.t1_drop_launch import build_scene
    elif tid == "T2_blast_wind":
        from templates.t2_blast_wind import build_scene
    elif tid == "T3_hydraulic_crush":
        from templates.t3_hydraulic_crush import build_scene
    elif tid == "T4_scale_drop":
        from templates.t4_scale_drop import build_scene
    elif tid == "T5_chain_domino":
        from templates.t5_chain_domino import build_scene
    else:
        raise ValueError(f"Unknown template: {tid}")

    scene, preview_frames = build_scene(spec, samples=args.samples)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("[runner] pack_all warning:", e, flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"[runner] Saved blend: {blend_path}", flush=True)

    if args.preview_only:
        for label, fnum in preview_frames:
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(frames_dir, f"preview_{label}.png")
            bpy.ops.render.render(write_still=True)
        return

    if args.render_all:
        total = int(spec.get("total_frames", 150))
        for fnum in range(1, total + 1):
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(frames_dir, f"frame_{fnum:04d}.png")
            bpy.ops.render.render(write_still=True)
            if fnum % 30 == 0 or fnum == total or fnum <= 2:
                print(f"[{spec['id']}] Rendered {fnum}/{total}", flush=True)


def _host_main() -> None:
    p = argparse.ArgumentParser(description="Unified 5-Template Viral 3D Physics Runner")
    p.add_argument("--spec", required=True)
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    p.add_argument("--assemble", action="store_true")
    args = p.parse_args()

    spec_abs = os.path.abspath(args.spec)
    with open(spec_abs, "r", encoding="utf-8") as f:
        spec = json.load(f)

    out_dir = os.path.join(ROOT, "outputs", spec["id"])
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    mode_flag = "--preview-only" if args.preview_only else "--render-all"
    master_blend = "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/waterblob_mcp_master.blend"
    base_args = [BLENDER_BIN, "--background"]
    if spec["template"] == "T1_drop_launch" and os.path.exists(master_blend):
        base_args.append(master_blend)
    else:
        base_args.append("--factory-startup")

    cmd = [
        *base_args,
        "--python-exit-code", "1",
        "--python", os.path.abspath(__file__),
        "--",
        "--spec", spec_abs,
        "--samples", str(args.samples),
        mode_flag,
    ]
    subprocess.run(cmd, check=True)

    if args.preview_only:
        import glob
        from core.post_assemble import stitch_preview_grid
        previews = sorted(glob.glob(os.path.join(frames_dir, "preview_*.png")))
        qa_png = os.path.join(out_dir, "qa_preview_4frames.png")
        stitch_preview_grid(previews, qa_png)
        print(f"[{spec['id']}] Saved 4-frame Visual Gate sheet: {qa_png}", flush=True)
        return

    fps = int(spec.get("fps", 30))
    raw_mp4 = os.path.join(out_dir, f"{spec['id']}_raw.mp4")
    subprocess.run([
        FFMPEG_BIN, "-y", "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(fps),
        raw_mp4,
    ], check=True)
    print(f"[{spec['id']}] Encoded raw MP4: {raw_mp4}", flush=True)

    if args.assemble:
        from core.post_assemble import assemble_template_video
        final_mp4 = os.path.join(out_dir, f"{spec['id']}_final.mp4")
        strip_png = os.path.join(out_dir, f"qa_{spec['id']}_strip.png")
        assemble_template_video(spec, out_dir, raw_mp4, final_mp4, strip_png)
        print(f"[{spec['id']}] Assembled final MP4: {final_mp4}", flush=True)
        print(f"[{spec['id']}] Assembled strip PNG: {strip_png}", flush=True)


if __name__ == "__main__":
    if _inside_blender():
        _blender_main()
    else:
        _host_main()
