"""Google 영상 모델로 이야기 장면(반전 전) 클립을 만든다 — 실험용.

backend/app/genai_provider.py 의 GenAIMediaProvider 를 그대로 빌려 쓴다(backend 코드는 수정하지 않음).
반전(제품) 장면은 만들지 않는다: 그 장면은 기존 3D 컷을 쓴다.

사용:
  .venv/Scripts/python scripts/gclips.py <project_id> <round> [--dry-run]
결과:
  out/<project_id>/round-<n>/gclips/ref.jpg        스타일·주인공 참고 이미지 (이미지 모델)
  out/<project_id>/round-<n>/gclips/beat<k>.mp4    장면 클립 (영상 모델)
  out/<project_id>/round-<n>/gclips/meta.json      프롬프트, 모델, 소요 시간
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

B_DIR = Path(__file__).resolve().parents[1]
BACKEND = B_DIR.parents[1]  # nepda.official/backend


def load_env(path: Path) -> None:
    """b/.env 를 읽어 환경변수로 (값은 출력하지 않는다)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and k not in os.environ:
                os.environ[k] = v


# 모든 클립에 똑같이 붙이는 스타일 가이드 (3D 컷·반전 장면과 톤을 맞춘다)
STYLE = """STYLE GUIDE (apply to every shot, keep identical across shots):
- Look: stylized 3D animation, soft clay / low-poly feel, simple clean shapes, matte materials. NOT photorealistic, no realistic human skin.
- Palette: white, light gray, charcoal black, plus ONE accent color: vivid red (#e8322a). No other saturated colors,
  unless the story itself needs them (e.g. a rainbow) — then keep those colors soft and muted, and keep red as the strongest color.
- Lighting: soft studio key light, gentle shadows, plain dark charcoal background (#0b0b10 to #1a1a22).
- Framing: vertical 9:16. Main subject in the UPPER two thirds of the frame. Keep the bottom third calm and empty (subtitles go there).
- Camera: one continuous shot, slow push-in or slow orbit. No cuts inside the clip.
- FORBIDDEN: any readable text, letters, numbers or digits in the image; logos; real brand marks; timers, clocks or watch dials.
"""


def scene_prompt(title: str, beat: dict, story_seed: str | None, k: int, n: int) -> str:
    s3 = beat.get("scene3d") or {}
    fact = s3.get("fact_shown") or ""
    motion = "; ".join(m.get("action", "") for m in sorted(s3.get("motion", []), key=lambda m: m.get("from", 0)))
    return (
        f"{STYLE}\n"
        f"STORY (one knowledge story told over {n} shots): {story_seed or title}\n"
        f"THIS SHOT ({k}/{n}): {beat.get('visual', '')}\n"
        f"What the viewer must understand: {fact}\n"
        f"Motion to show: {motion}\n"
        f"Narration heard over this shot (Korean, for context only, do NOT render as text): {beat.get('narration', '')}\n"
        f"Keep the same main character, look and palette as the reference image."
    )


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    project, rnd = sys.argv[1], int(sys.argv[2])
    dry = "--dry-run" in sys.argv
    load_env(B_DIR / ".env")
    if not dry and not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY 가 b/.env 에 없습니다.")
        return 1

    rec = json.loads((B_DIR / "out" / project / f"round-{rnd}.json").read_text(encoding="utf-8"))
    sc = rec["response"]["scenarios"][0]
    beats = sorted(sc["beats"], key=lambda b: b["order"])
    story = beats[:-1]  # 반전(마지막) 장면은 3D 컷 사용
    seed = sc["ad_spec"].get("story_seed")
    out = B_DIR / "out" / project / f"round-{rnd}" / "gclips"
    out.mkdir(parents=True, exist_ok=True)

    ref_prompt = (
        f"{STYLE}\nA single character/style reference frame for this story: {seed or sc['hook_title']}. "
        f"Show the main character (or main object) of the story, full body, centered in the upper two thirds, plain background."
    )
    prompts = [scene_prompt(sc["hook_title"], b, seed, i + 1, len(story)) for i, b in enumerate(story)]
    if dry:
        print("=== ref\n" + ref_prompt)
        for b, p in zip(story, prompts):
            print(f"\n=== beat {b['order']} ({b['duration_sec']}s → {max(3, min(15, math.ceil(b['duration_sec'])))}s)\n{p}")
        return 0

    sys.path.insert(0, str(BACKEND))
    from app.config import Settings  # noqa: E402
    from app.genai_provider import GenAIMediaProvider  # noqa: E402

    settings = Settings()
    gp = GenAIMediaProvider(settings)
    meta: dict = {"image_model": settings.image_model, "video_model": settings.video_model, "clips": []}

    t0 = time.monotonic()
    ref = gp.generate_reference_image(ref_prompt, out / "ref.jpg", aspect_ratio="9:16", mime_type="image/jpeg")
    meta["ref"] = {"path": "ref.jpg", "elapsed_sec": ref.elapsed_sec, "skipped": ref.skipped, "prompt": ref_prompt}
    print(f"[gclips] 참고 이미지 {ref.elapsed_sec}s{' (기존 파일)' if ref.skipped else ''}")

    for b, p in zip(story, prompts):
        dur = max(3, min(15, math.ceil(b["duration_sec"])))
        r = gp.generate_video_clip(p, out / f"beat{b['order']}.mp4", aspect_ratio="9:16", duration_sec=dur,
                                   resolution="720p", reference_paths=[out / "ref.jpg"])
        meta["clips"].append({"order": b["order"], "path": f"beat{b['order']}.mp4", "requested_sec": dur,
                              "elapsed_sec": r.elapsed_sec, "skipped": r.skipped, "bytes": r.bytes_written, "prompt": p})
        print(f"[gclips] 장면 {b['order']} {dur}s 클립 {r.elapsed_sec}s{' (기존 파일)' if r.skipped else ''}")

    meta["total_elapsed_sec"] = round(time.monotonic() - t0, 1)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gclips] 완료 {meta['total_elapsed_sec']}s → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
