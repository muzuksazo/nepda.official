#!/usr/bin/env python3
"""Deterministic Google Flow job generator & credit-quote builder for 05_ad_spec.json.

Reads flow_anchors and variant flow_hook definitions from 05_ad_spec.json and builds:
  1. 05_jobs.json compatible 1-to-1 with flow_automator.py (Nano Banana 2 Lite 0 cr refs +
     Omni 1.2 Flash x1 units with enforced 6-layer Zero-Text tail).
  2. Optional 05_credit_quote.md showing 360p vs 720p parallel wave credit breakdown
     and copy-pasteable flow_automator.py commands.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from typing import Any, Dict, List

ZERO_TEXT_TAIL = (
    "No camera cuts, zero readable text, no typography, no subtitles, "
    "no watermarks, no logos, no music."
)

NO_SIGH_TAIL = "Calm grounded hands and natural neutral posture."

VISUAL_STYLE_PRESETS: Dict[str, Dict[str, str]] = {
    "blender_clay_diorama": {
        "ref_prefix": (
            "Stylized Blender Cycles 3D matte polymer-clay miniature diorama still render "
            "(subtle tactile clay fingerprint micro-texture, sculpted miniature props, "
            "tilt-shift shallow depth of field, zero photorealistic human skin or real photography)."
        ),
        "video_prefix": (
            "Stylized Blender Cycles 3D matte clay stop-motion-feel animation render "
            "(smooth 3D miniature character and diorama physics, soft global illumination, "
            "zero photorealistic human faces or uncanny live-action artifacts)."
        ),
    },
    "blender_3d_cutaway": {
        "ref_prefix": (
            "Clean Blender Cycles 3D scientific educational cutaway render on matte "
            "ceramic/clay materials with translucent volumetric fluid/airflow shaders, "
            "soft studio rim lighting, zero live-action photography or human faces."
        ),
        "video_prefix": (
            "Smooth Blender Cycles 3D isometric scientific cutaway animation render "
            "(clean matte 3D geometry, physically clear translucent fluid particles, "
            "crisp studio lighting, zero photorealistic humans)."
        ),
    },
    "blender_isometric_toy": {
        "ref_prefix": (
            "Stylized Blender Cycles 3D isometric vinyl-toy miniature room render "
            "(clean beveled pastel/matte geometry, soft studio area lights, "
            "zero photorealistic human skin or messy live-action clutter)."
        ),
        "video_prefix": (
            "Smooth Blender Cycles 3D isometric vinyl-toy miniature animation render "
            "(snappy stylized 3D motion, clean soft studio shadows, "
            "zero photorealistic human actors)."
        ),
    },
}


def _apply_visual_style(prompt: str, visual_style: Optional[str], kind: str) -> str:
    p = (prompt or "").strip()
    if not visual_style or visual_style not in VISUAL_STYLE_PRESETS:
        return p
    if "blender" in p.lower():
        return p
    prefix = VISUAL_STYLE_PRESETS[visual_style][f"{kind}_prefix"]
    return f"{prefix} {p}".strip()


def _ensure_zero_text(prompt: str, *, include_no_sigh: bool = False) -> str:
    p = (prompt or "").strip()
    low = p.lower()
    if "zero readable text" not in low and "no readable text" not in low:
        p = p.rstrip(".") + ". " + ZERO_TEXT_TAIL
    if include_no_sigh and "no visible sigh" not in low:
        p = p.rstrip(".") + " " + NO_SIGH_TAIL
    return p.strip()


def _seg_dur(seg: Dict[str, Any]) -> float:
    if seg.get("type") == "source" and "src_start" in seg and "src_end" in seg:
        spd = float(seg.get("speed", 1.0) or 1.0)
        return max(0.05, (float(seg["src_end"]) - float(seg["src_start"])) / max(spd, 0.01))
    return max(0.05, float(seg.get("duration", 1.0) or 1.0))


def build_flow_jobs(spec: Dict[str, Any], *, res: str = "360p") -> Dict[str, Any]:
    ar = spec.get("aspect_ratio", "9:16") or "9:16"
    spec_style = spec.get("visual_style")
    per_sec_cr = 1 if res == "360p" else 3
    refs: List[Dict[str, Any]] = []
    units: List[Dict[str, Any]] = []

    anchors = spec.get("flow_anchors") or []
    seen_ref_ids = set()

    def _collect_segments() -> List[Tuple[str, Optional[str], Dict[str, Any]]]:
        items: List[Tuple[str, Optional[str], Dict[str, Any]]] = []
        for vk, v in (spec.get("variants") or {}).items():
            if not isinstance(v, dict):
                continue
            v_style = v.get("visual_style") or spec_style
            for seg in v.get("hook_segments") or []:
                items.append((vk, v_style, seg))
        if spec.get("timeline"):
            t_vk = spec.get("output_stem") or spec.get("project_id") or "master"
            for seg in spec.get("timeline") or []:
                items.append((t_vk, spec_style, seg))
        return items

    for vk, parent_style, seg in _collect_segments():
        if not isinstance(seg, dict) or seg.get("type") != "flow_video":
            continue
        seg_style = seg.get("visual_style") or parent_style
        uid = seg.get("flow_unit_id") or seg.get("id") or f"G_{vk}"
        ref_id = seg.get("flow_ref_id") or f"R_{uid}"
        ref_prompt = seg.get("flow_ref_prompt") or ""
        vid_prompt = seg.get("flow_video_prompt") or ""
        attach_ids = list(seg.get("attach_ids") or [])
        human_present = bool(seg.get("human_present", False))

        if ref_prompt and ref_id not in seen_ref_ids:
            seen_ref_ids.add(ref_id)
            styled_ref = _apply_visual_style(ref_prompt, seg_style, "ref")
            ref_entry: Dict[str, Any] = {
                "id": ref_id,
                "file": f"refs/{ref_id}.png",
                "model": "nano_banana_2_lite",
                "count": 1,
                "settings": {"aspect_ratio": ar},
                "prompt": _ensure_zero_text(styled_ref, include_no_sigh=human_present),
            }
            if attach_ids:
                ref_entry["attach_ids"] = attach_ids
            refs.append(ref_entry)

        raw_d = _seg_dur(seg)
        req_dur = int(seg.get("flow_duration_sec") or max(3, min(15, int(math.ceil(raw_d)))))
        req_dur = max(3, min(15, req_dur))
        mode = seg.get("flow_mode") or "ingredients"
        styled_vid = _apply_visual_style(vid_prompt, seg_style, "video")
        unit_entry: Dict[str, Any] = {
            "id": uid,
            "variant": vk,
            "mode": mode,
            "model": "omni_1_2_flash",
            "count": 1,
            "reference_ids": [ref_id] if ref_id in seen_ref_ids or any(a.get("id") == ref_id for a in anchors) else attach_ids,
            "settings": {"aspect_ratio": ar, "resolution": res, "duration_sec": req_dur},
            "est_credits": req_dur * per_sec_cr,
            "outputs": [seg.get("path") or f"clips/{uid}_t1.mp4"],
            "prompt": _ensure_zero_text(styled_vid, include_no_sigh=human_present),
        }
        if mode == "frames":
            if seg.get("first_frame"):
                unit_entry["first_frame"] = seg["first_frame"]
            elif ref_id:
                unit_entry["first_frame"] = ref_id
            if seg.get("last_frame"):
                unit_entry["last_frame"] = seg["last_frame"]
        units.append(unit_entry)

    out: Dict[str, Any] = {
        "project_id": spec.get("project_id", ""),
        "aspect_ratio": ar,
        "resolution": res,
        "anchors": anchors,
        "references": refs,
        "units": units,
    }
    if spec_style:
        out["visual_style"] = spec_style
    return out


def format_credit_quote(jobs: Dict[str, Any], spec: Dict[str, Any]) -> str:
    pid = jobs.get("project_id", "")
    anchors = jobs.get("anchors") or []
    refs = jobs.get("references") or []
    units = jobs.get("units") or []
    src_video = spec.get("source_video") or "<SOURCE_MP4>"

    tot_360 = sum(int(u["settings"]["duration_sec"]) * 1 for u in units)
    tot_720 = sum(int(u["settings"]["duration_sec"]) * 3 for u in units)
    ref_ids = ",".join(r["id"] for r in refs)
    unit_ids = ",".join(u["id"] for u in units)

    lines = [
        f"# Google Flow Hook Credit Quote — `{pid}`",
        "",
        f"> Scope: `0-5s` hooks ONLY (`5-25s` body reuses real source footage at `0 cr`). Mode: `Omni 1.2 Flash` (`x1` enforced) + `Nano Banana 2 Lite` (`0 cr`).",
        "",
        "## 1. Real-Source Anchor Frames (`0 cr`, via `extract-first-frame`)",
        "",
        "| Asset ID | Source Timestamp | Output | Purpose |",
        "|---|---|---|---|",
    ]
    if anchors:
        for a in anchors:
            lines.append(
                f"| `{a['id']}` | `{a.get('time_sec', 0)}s` | `{a.get('file', 'refs/' + a['id'] + '.png')}` | {a.get('purpose', 'Product/bridge reference')} |"
            )
    else:
        lines.append("| (none) | - | - | No source anchors declared |")

    lines.extend([
        "",
        "## 2. Hook Keyframe Plates (`Nano Banana 2 Lite`, `0 cr`, `x1`)",
        "",
        "| Ref ID | Attach Anchors | Output | Credits |",
        "|---|---|---|---|",
    ])
    for r in refs:
        att = ",".join(r.get("attach_ids") or []) or "(none)"
        lines.append(f"| `{r['id']}` | `{att}` | `{r['file']}` | `0 cr` |")

    lines.extend([
        "",
        "## 3. Opening Motion Clips (`Omni 1.2 Flash`, Parallel 1-Wave `--concurrency 3`)",
        "",
        "| Unit | Variant | Mode | Duration | `360p` Cost | `720p` Cost | Output |",
        "|---|---|---|---|---|---|---|",
    ])
    for u in units:
        d = int(u["settings"]["duration_sec"])
        lines.append(
            f"| `{u['id']}` | `{u.get('variant', '')}` | `{u['mode']}` | `{d}s` | `{d} cr` | `{d * 3} cr` | `{u['outputs'][0]}` |"
        )
    lines.extend([
        f"| **TOTAL** | **{len(units)} hooks** | **1-wave parallel** | - | **`{tot_360} cr`** | **`{tot_720} cr`** | - |",
        "",
        "## 4. Exact Run Commands (After Explicit User Approval)",
        "",
        "```bash",
        "SCRIPTS=${CLAUDE_PLUGIN_ROOT}/libraries/media-tools",
    ])
    for a in anchors:
        out_rel = a.get("file") or f"refs/{a['id']}.png"
        lines.append(
            f"python3 \"$SCRIPTS/flow_automator.py\" extract-first-frame --project <PROJECT_DIR> --video \"{src_video}\" --time {a.get('time_sec', 0)} --id {a['id']} --out \"{out_rel}\""
        )
    if ref_ids:
        lines.append(
            f"python3 \"$SCRIPTS/flow_automator.py\" refs --tab <TAB_ID> --project <PROJECT_DIR> --ids \"{ref_ids}\" --log"
        )
        lines.append(
            "python3 \"$SCRIPTS/flow_automator.py\" contact-sheet --project <PROJECT_DIR> --out refs/sheet.png"
        )
    if unit_ids:
        cap = tot_360 if jobs.get("resolution") == "360p" else tot_720
        lines.append(
            f"python3 \"$SCRIPTS/flow_automator.py\" video-batch --tab <TAB_ID> --project <PROJECT_DIR> --ids \"{unit_ids}\" --concurrency 3 --max-credits {cap} --log"
        )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Build 05_jobs.json & credit quote from 05_ad_spec.json")
    p.add_argument("--spec", required=True)
    p.add_argument("--out-jobs", required=True)
    p.add_argument("--out-quote", default=None)
    p.add_argument("--res", choices=["360p", "720p"], default="360p")
    args = p.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    jobs = build_flow_jobs(spec, res=args.res)
    os.makedirs(os.path.dirname(os.path.abspath(args.out_jobs)), exist_ok=True)
    with open(args.out_jobs, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    if args.out_quote:
        q = format_credit_quote(jobs, spec)
        os.makedirs(os.path.dirname(os.path.abspath(args.out_quote)), exist_ok=True)
        with open(args.out_quote, "w", encoding="utf-8") as f:
            f.write(q)

    tot_cr = sum(int(u.get("est_credits", 0)) for u in jobs["units"])
    print(
        json.dumps(
            {
                "jobs": os.path.abspath(args.out_jobs),
                "quote": os.path.abspath(args.out_quote) if args.out_quote else None,
                "anchors": len(jobs["anchors"]),
                "refs_0cr": len(jobs["references"]),
                "units": len(jobs["units"]),
                "resolution": args.res,
                "total_est_credits": tot_cr,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
