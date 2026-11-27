"""훅 영상 한 편, 자체 호스팅 모델로: 시나리오(Claude) → 스틸컷(FLUX) → 장면 클립(MiniMax) → 나레이션·자막 조립. 유료.

    python backend/selfhosted/hook_cycle.py <product.json> <out_dir> [--type B] [--ref 제품사진 ...] [--scenario cycle.json]

1·2단계는 still_cycle.cycle, 4단계는 still_cycle.assemble(서버 훅 조립 코드 그대로, Inworld TTS), 3단계는 minimax_modal.
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

CLIP_W, CLIP_H = 576, 1024
NO_VOICE = "Sound: natural ambient sound effects only. No speech, no voice, no singing, no music."


def frames_for(seconds: float) -> int:
    n = max(5, round(seconds * 24))
    return n + (5 - n % 17) % 17


def motion_from(spec: str) -> str:
    """장면 프롬프트에서 나레이션 줄을 빼고 소리 규칙을 붙인다 (MiniMax 는 소리도 만들어 문장을 말소리로 지어낸다)."""
    lines = [l for l in spec.splitlines() if not l.startswith("Narration heard over this shot")]
    return "\n".join(lines + [NO_VOICE])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("out_dir")
    ap.add_argument("--type", default="B")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--scenario", help="저장된 cycle.json 의 시나리오 재사용")
    args = ap.parse_args()

    import modal

    import minimax_modal
    import still_cycle

    product = json.loads(Path(args.product).read_text(encoding="utf-8"))
    refs = {Path(p).name: Path(p).read_bytes() for p in args.ref}
    given = json.loads(Path(args.scenario).read_text(encoding="utf-8"))["scenarios"] if args.scenario else None
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # 1·2) 시나리오 → 대표 컷 → 장면별 스틸컷
    with still_cycle.app.run():
        result = still_cycle.cycle.remote(product, [args.type.upper()], refs, ["claude"], given, "flux")
    for line in result["log"]:
        print(line, flush=True)
    if not result["scenarios"]:
        raise SystemExit("시나리오를 만들지 못했습니다.")
    scenario = result["scenarios"][0]
    stills = {s["name"]: s for s in result["stills"]}
    for s in result["stills"]:
        (out / f"{s['name']}.png").write_bytes(base64.b64decode(s["png"]))
    (out / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[스틸컷] {len(stills)}장 {time.time() - t0:.0f}초", flush=True)

    # 3) 장면 클립 (장면마다 컨테이너가 동시에)
    beats = sorted(scenario["beats"], key=lambda b: int(b.get("order") or 0))
    calls, orders = [], []
    for i, beat in enumerate(beats, start=1):
        st = stills.get(f"beat{i}")
        if not st:
            continue
        seconds = float(beat.get("duration_sec") or 4.0) + 1.0  # 나레이션에 맞춰 장면이 늘어날 여유
        calls.append((base64.b64decode(st["png"]), motion_from(st["spec"]), CLIP_W, CLIP_H, frames_for(seconds), 20, 1))
        orders.append(int(beat.get("order") or i))
    t1 = time.time()
    with minimax_modal.app.run():
        clip_bytes = list(minimax_modal.render.starmap(calls))
    clips = {}
    for order, data in zip(orders, clip_bytes):
        (out / f"clip{order}.mp4").write_bytes(data)
        clips[str(order)] = data
    print(f"[클립] {len(clips)}개 {time.time() - t1:.0f}초", flush=True)

    # 4) 나레이션·자막 조립 (서버 훅 조립 코드)
    t2 = time.time()
    with still_cycle.app.run():
        hook = still_cycle.assemble.remote(scenario, product, clips)
    (out / "hook.mp4").write_bytes(hook["hook_mp4"])
    (out / "hook.srt").write_text(hook["srt"], encoding="utf-8")
    print(f"[조립] {hook['duration']}초짜리 훅, {time.time() - t2:.0f}초, 경고={hook['warnings']}", flush=True)
    print(f"[끝] 전체 {time.time() - t0:.0f}초 → {out / 'hook.mp4'}", flush=True)


if __name__ == "__main__":
    main()
