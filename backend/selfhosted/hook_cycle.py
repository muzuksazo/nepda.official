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
    ap.add_argument("--steps", type=int, default=8, help="MiniMax 단계 수 (8 이하면 터보 LoRA)")
    ap.add_argument("--footage", action="append", default=[], help="촬영본 (주면 공용 본편 약 10초를 훅 뒤에 붙인다)")
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
    (out / "prompts.json").write_text(json.dumps(
        {s["name"]: {"frame": s.get("caption"), "motion": s.get("motion")} for s in result["stills"]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    phase1 = time.time() - t0
    print(f"[스틸컷] {len(stills)}장 {phase1:.0f}초  ← ① 시나리오→콘티 (사용자가 기다리는 구간)", flush=True)

    # 3) 장면 클립 (장면마다 컨테이너가 동시에)
    beats = sorted(scenario["beats"], key=lambda b: int(b.get("order") or 0))
    calls, orders = [], []
    for i, beat in enumerate(beats, start=1):
        st = stills.get(f"beat{i}")
        if not st:
            continue
        seconds = float(beat.get("duration_sec") or 4.0) + 1.0  # 나레이션에 맞춰 장면이 늘어날 여유
        # Claude 가 쓴 영어 움직임 묘사(글자를 부르는 말 없음). 없을 때만 예전 방식
        motion = st.get("motion") or motion_from(st["spec"])
        calls.append((base64.b64decode(st["png"]), motion, CLIP_W, CLIP_H, frames_for(seconds), args.steps, 1))
        orders.append(int(beat.get("order") or i))
    with minimax_modal.app.run():
        service = minimax_modal.MiniMax()
        # 실제 서비스에서는 콘티 확인 화면이 뜰 때 미리 켠다 (생성은 확인 뒤). 여기서는 바로 이어서 잰다
        tw = time.time()
        warm = list(service.warm.map(range(len(calls))))
        print(f"[미리 켜기] GPU {len(warm)}대 {time.time() - tw:.0f}초 (확인하는 동안 일어나는 구간)", flush=True)
        t1 = time.time()
        clip_bytes = list(service.render.starmap(calls))
    clips = {}
    for order, data in zip(orders, clip_bytes):
        (out / f"clip{order}.mp4").write_bytes(data)
        clips[str(order)] = data
    t_clips = time.time() - t1
    print(f"[클립] {len(clips)}개 {t_clips:.0f}초", flush=True)

    # 4) 나레이션·자막 조립 (서버 훅 조립 코드)
    t2 = time.time()
    with still_cycle.app.run():
        footage = {Path(p).name: Path(p).read_bytes() for p in args.footage} or None
        hook = still_cycle.assemble.remote(scenario, product, clips, footage)
    (out / "hook.mp4").write_bytes(hook["hook_mp4"])
    if hook.get("final_mp4"):
        (out / "final.mp4").write_bytes(hook["final_mp4"])
        print(f"[본편] {hook['body_sec']}초 붙임 → final.mp4, 경고={hook['body_warnings']}", flush=True)
    (out / "hook.srt").write_text(hook["srt"], encoding="utf-8")
    t_asm = time.time() - t2
    print(f"[조립] {hook['duration']}초짜리 훅, {t_asm:.0f}초, 경고={hook['warnings']}", flush=True)
    print(f"[끝] ① {phase1:.0f}초 + ② {t_clips + t_asm:.0f}초 (클립 {t_clips:.0f} + 조립 {t_asm:.0f}), "
          f"전체 {time.time() - t0:.0f}초 → {out / 'hook.mp4'}", flush=True)


if __name__ == "__main__":
    main()
