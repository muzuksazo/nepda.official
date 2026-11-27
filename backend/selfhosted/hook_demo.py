"""시나리오 하나 → 장면별 첫 프레임(FLUX klein) → 장면별 클립(MiniMax-H3), 전부 Modal H100. 내부 시험용 (유료).

    python backend/selfhosted/hook_demo.py <scenario.json> <out_dir> [--product product.json] [--ref 제품사진.png ...]

프롬프트는 hookpipe/prompts.py 의 first_frame_prompt / motion_prompt (훅 파이프라인과 같은 규칙).
제품 장면(product_beat_orders)은 --ref 제품 사진을 FLUX 참고 이미지로 넣는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # backend/
sys.path.insert(0, str(HERE))

from hookpipe.prompts import first_frame_prompt, motion_prompt, ordered_beats, product_beat_orders  # noqa: E402

FRAME_W, FRAME_H = 768, 1376  # FLUX 첫 프레임
CLIP_W, CLIP_H = 576, 1024  # MiniMax 클립 (32 배수, 첫 프레임과 비율 거의 같음)


def frames_for(seconds: float) -> int:
    n = max(5, round(seconds * 24))
    return n + (5 - n % 17) % 17  # MiniMax 공식 템플릿의 17k+5 규칙


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("out_dir")
    ap.add_argument("--product", help="제품 정보 JSON (name, call_name, verified_facts)")
    ap.add_argument("--ref", action="append", default=[], help="제품 사진 (제품 장면의 FLUX 참고 이미지)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    product = json.loads(Path(args.product).read_text(encoding="utf-8")) if args.product else None
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    beats = ordered_beats(scenario)
    product_orders = set(product_beat_orders(scenario))
    refs = {f"ref{i}{Path(p).suffix}": Path(p).read_bytes() for i, p in enumerate(args.ref)}
    ref_name = next(iter(refs), None)

    jobs, plans = [], []
    for beat in beats:
        order = int(beat.get("order") or 0)
        shows = order in product_orders
        use_ref = shows and ref_name is not None
        job = {
            "name": f"beat{order}",
            "seed": args.seed,
            "width": FRAME_W,
            "height": FRAME_H,
            "prompt": first_frame_prompt(scenario, beat, product=product, shows_product=shows,
                                         has_product_reference=use_ref),
        }
        if use_ref:
            job["image"] = ref_name
        jobs.append(job)
        plans.append({"order": order, "seconds": float(beat.get("duration_sec") or 4.0),
                      "motion": motion_prompt(scenario, beat, shows_product=shows), "frame_prompt": job["prompt"]})
    (out / "prompts.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")

    import flux_modal
    import minimax_modal

    t0 = time.time()
    with flux_modal.app.run():
        frames = flux_modal.render.remote(jobs, refs)
    for name, data in frames.items():
        (out / f"{name}_frame.png").write_bytes(data)
    print(f"[첫 프레임] {len(frames)}장 {time.time() - t0:.0f}초", flush=True)

    t1 = time.time()
    calls = [(frames[f"beat{p['order']}"], p["motion"], CLIP_W, CLIP_H, frames_for(p["seconds"]), 20, args.seed)
             for p in plans]
    with minimax_modal.app.run():
        clips = list(minimax_modal.MiniMax().render.starmap(calls))  # 장면별 컨테이너가 동시에 돈다
    for plan, data in zip(plans, clips):
        (out / f"beat{plan['order']}.mp4").write_bytes(data)
    print(f"[클립] {len(clips)}개 {time.time() - t1:.0f}초 (전체 {time.time() - t0:.0f}초) → {out}", flush=True)


if __name__ == "__main__":
    main()
