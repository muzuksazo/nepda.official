"""Gemini 로 만든 훅을 자체 호스팅 모델로 똑같이 다시 만든다 (비교용, 유료).

    python backend/selfhosted/replay_hook.py <훅 폴더> <out_dir> [--style-ref 대표이미지.jpg]

<훅 폴더>/render_meta.json 에 남은 장면별 프롬프트를 그대로 쓴다.
- 첫 프레임: FLUX klein (배포된 napda-flux3-klein, PUP 끔). 참고 이미지도 그때와 같게:
  제품 장면 = render_meta.product_refs, 나머지 = 이야기 대표 이미지(style_ref, 없으면 Gemini 와 같은 프롬프트로 FLUX 가 1장 생성)
- 움직임: MiniMax-H3, 같은 프롬프트에서 나레이션 줄만 뺀다 (소리까지 만드는 모델이라 문장을 말소리로 지어낸다)
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from hookpipe.prompts import reference_image_prompt  # noqa: E402

FRAME_W, FRAME_H = 768, 1376
CLIP_W, CLIP_H = 576, 1024
NO_VOICE = "Sound: natural ambient sound effects only. No speech, no voice, no singing, no music."


def frames_for(seconds: float) -> int:
    n = max(5, round(seconds * 24))
    return n + (5 - n % 17) % 17


def motion_from(prompt: str) -> str:
    lines = [l for l in prompt.splitlines() if not l.startswith("Narration heard over this shot")]
    return "\n".join(lines + [NO_VOICE])


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hook_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--style-ref", help="이야기 대표 이미지 (없으면 render_meta.style_ref → 그래도 없으면 FLUX 로 생성)")
    ap.add_argument("--flux-style-ref", action="store_true", help="대표 이미지를 Gemini 것 대신 FLUX 로 새로 만든다")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    import modal

    hook = Path(args.hook_dir)
    meta = json.loads((hook / "render_meta.json").read_text(encoding="utf-8"))
    scenario = json.loads((hook / "scenario.json").read_text(encoding="utf-8"))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def local(p: str) -> Path:
        q = Path(p)
        return q if q.is_file() else hook / "_work" / "refs" / q.name

    product_refs = [local(p) for p in meta.get("product_refs") or []]
    product_refs = [p for p in product_refs if p.is_file()]
    flux = modal.Cls.from_name("napda-flux3-klein", "Flux3KleinService")()

    def flux_image(prompt: str, refs: list[Path], name: str) -> bytes:
        t = time.time()
        res = flux.run_generate.remote({
            "prompt": prompt, "reference_images": [_b64(r) for r in refs], "width": FRAME_W, "height": FRAME_H,
            "seed": args.seed, "use_pup": False, "safety": True, "output_format": "png",
        })
        data = base64.b64decode(res["image_base64"])
        (out / f"{name}.png").write_bytes(data)
        print(f"[{name}] {time.time() - t:.0f}초 (FLUX {res['latency_ms']}ms)", flush=True)
        return data

    t0 = time.time()
    saved = meta.get("style_ref")  # 예전 render_meta 는 경로 대신 True/False 만 남겼다
    style = Path(args.style_ref) if args.style_ref else (local(saved) if isinstance(saved, str) else None)
    if args.flux_style_ref or not (style and style.is_file()):
        flux_image(reference_image_prompt(scenario), [], "style_ref")
        style = out / "style_ref.png"

    calls, plans = [], []
    for beat in meta["beats"]:
        order = int(beat["order"])
        refs = product_refs if beat.get("shows_product") and product_refs else [style]
        frame = flux_image(beat["prompt"], refs, f"beat{order}_frame")
        motion = motion_from(beat["prompt"])
        plans.append({"order": order, "frame_refs": [r.name for r in refs], "frame_prompt": beat["prompt"], "motion": motion})
        calls.append((frame, motion, CLIP_W, CLIP_H, frames_for(float(beat.get("duration") or 4.0)), 20, args.seed))
    (out / "prompts.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[첫 프레임] {len(calls)}장 {time.time() - t0:.0f}초", flush=True)

    import minimax_modal

    t1 = time.time()
    with modal.enable_output(), minimax_modal.app.run():
        clips = list(minimax_modal.render.starmap(calls))
    for plan, data in zip(plans, clips):
        (out / f"beat{plan['order']}.mp4").write_bytes(data)
    print(f"[클립] {len(clips)}개 {time.time() - t1:.0f}초 (전체 {time.time() - t0:.0f}초) → {out}", flush=True)


if __name__ == "__main__":
    main()
