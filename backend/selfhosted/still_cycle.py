"""한 바퀴: 시나리오 생성(B·C 작업자, Claude) → 장면별 프롬프트 → 장면 묘사 변환(Claude·Gemini) → 스틸컷(FLUX). 영상은 만들지 않는다.

    python backend/selfhosted/still_cycle.py <product.json> <out_dir> [--types B,C] [--ref 제품사진.png ...]
        [--captioner claude,gemini]

- 서버와 같은 이미지(backend/Dockerfile)·Secret(napda-backend)으로 Modal 에서 돈다. 키는 서버에만 있다.
- 글 모델: HOOK_WORKER_LLM 만 이 실행에서 Claude 로 바꾼다 (Gemini AI Studio 선불 크레딧 소진).
  Gemini 장면 묘사는 Vertex(WIF, Secret 의 GOOGLE_GENAI_USE_VERTEXAI) 로 부른다.
- 스틸컷: 배포된 napda-flux3-klein. Gemini 훅과 같은 흐름 — 이야기 대표 컷 1장을 먼저 만들고,
  제품 장면은 제품 사진, 나머지 장면은 대표 컷을 참고 이미지로 넣는다.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path, PurePosixPath

import modal

# 내 PC: backend/selfhosted/still_cycle.py → 저장소 루트. Modal 컨테이너 안에서는 /root/still_cycle.py 라 상위 폴더가 모자란다
_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent
W, H = 768, 1376

image = modal.Image.from_dockerfile(ROOT / "backend" / "Dockerfile", context_dir=ROOT).env({
    "PYTHONPATH": "/app",
    "STORAGE_BACKEND": "local",  # 이 시험은 R2 에 쓰지 않는다
    "WORK_ROOT": "/tmp/napda/jobs",
    "OUTPUT_DIR": "/tmp/napda/outputs",
    "DB_PATH": "/tmp/napda/jobs.db",
})
app = modal.App("napda-still-cycle")
SHOT_PLAN = [
    "wide establishing shot that shows the whole place, subject small in the frame, seen from a high angle",
    "medium shot from a low side angle, subject from the waist up, a different part of the place in the background",
    "extreme close-up on the single key detail of the idea, shallow depth of field, background fully blurred",
    "over-the-shoulder or top-down view of the action, a fresh angle not used before",
]
SHOT_PRODUCT = "hero close-up of the product filling the middle of the frame, eye level, clean background"
# 뒤에 둔 Secret 이 같은 이름을 덮는다: 이 실행에서만 글 모델을 Claude 로
_override = {"HOOK_WORKER_LLM": "claude-opus-5-5"}
# STILL_GEMINI_VIA=apikey: Gemini 를 Vertex(WIF) 대신 AI Studio 키로 부른다 (모델 이름이 Vertex 에 없을 때 비교용)
import os as _os

if _os.environ.get("STILL_GEMINI_VIA", "").strip().lower() == "apikey":
    _override["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
override = modal.Secret.from_dict(_override)


@app.function(image=image, secrets=[modal.Secret.from_name("napda-backend"), override], cpu=2.0, memory=4096, timeout=3600)
def cycle(product: dict, hook_types: list, refs: dict, captioners: list, scenarios_in: list | None = None,
          engine: str = "flux", fixed_captions: dict | None = None) -> dict:
    import sys as _sys

    if "/app" not in _sys.path:
        _sys.path.insert(0, "/app")
    import uuid

    from app.config import Settings
    from hookpipe.flux_caption import motion_prompt_for_video, to_flux_caption
    from hookpipe.prompts import beat_prompt, ordered_beats, product_beat_orders, reference_image_prompt
    from hookpipe.workers import generate_with_worker

    settings = Settings()
    flux = modal.Cls.from_name("napda-flux3-klein", "Flux3KleinService")()
    product_refs = [base64.b64encode(b).decode("ascii") for b in refs.values()]
    project = {"project_id": f"still_{uuid.uuid4().hex[:8]}", "product": product, "selected_types": hook_types}
    log: list = []

    def note(msg: str) -> None:
        print(msg, flush=True)
        log.append(msg)

    # 대표 컷을 참고로 넣으면 FLUX 가 구도까지 베꼈다(2026-11-27): 인물 디자인만 가져오라고 앞에 붙인다
    STYLE_REF_LEAD = ("Use the reference image only for the character design, colors and materials. "
                      "Build a completely new composition, pose, setting detail and camera angle as described: ")

    def still(spec: str, ref_b64: list, captioner: str, name: str = "", style_ref: bool = False) -> dict:
        fixed = (fixed_captions or {}).get(name)
        if engine == "gemini":
            # 비교용: FLUX 때 쓴 장면 묘사를 그대로 주면 두 모델의 입력 글자가 같아진다
            return gemini_still(fixed or spec, ref_b64)
        t = time.time()
        cap = to_flux_caption(spec, provider=captioner, settings=settings)
        if style_ref:
            cap = STYLE_REF_LEAD + cap
        t_cap = time.time() - t
        res = flux.run_generate.remote({"prompt": cap, "reference_images": ref_b64, "width": W, "height": H,
                                        "seed": 1, "use_pup": False, "safety": True, "output_format": "png"})
        return {"caption": cap, "caption_sec": round(t_cap, 1), "flux_ms": res["latency_ms"], "png": res["image_base64"]}

    def gemini_still(spec: str, ref_b64: list) -> dict:
        """Gemini 이미지 모델 (Secret 설정 그대로: Vertex WIF 또는 API 키). 규칙 목록 프롬프트를 그대로 이해하므로 변환하지 않는다."""
        import tempfile

        from app.genai_provider import GenAIMediaProvider

        work = Path(tempfile.mkdtemp())
        anchors = []
        for i, b in enumerate(ref_b64):
            anchors.append(work / f"ref{i}.png")
            anchors[-1].write_bytes(base64.b64decode(b))
        target = work / "out.jpg"
        t = time.time()
        # Vertex 의 Gemini 이미지 모델은 결과 형식으로 JPEG 만 받는다 (훅 파이프라인도 JPEG 로 받는다)
        GenAIMediaProvider(settings).generate_reference_image(spec, target, aspect_ratio="9:16", anchor_paths=anchors,
                                                              mime_type="image/jpeg", skip_existing=False)
        return {"caption": spec, "caption_sec": 0.0, "flux_ms": int((time.time() - t) * 1000),
                "png": base64.b64encode(target.read_bytes()).decode("ascii")}

    out: dict = {"scenarios": [], "stills": [], "log": log}
    for hook_type in hook_types:
        t0 = time.time()
        given = [sc for sc in (scenarios_in or []) if str(sc.get("type")).upper() == hook_type]
        if given:
            items = given
        else:
            try:
                items = generate_with_worker(hook_type, project, settings, round_no=1, previous_scenarios=[])
            except Exception as exc:  # 한 유형이 실패해도 다른 유형은 계속
                note(f"[{hook_type}] 시나리오 실패: {exc}")
                continue
        scenario = items[0]
        out["scenarios"].append(scenario)
        note(f"[{hook_type}] 시나리오 {time.time() - t0:.0f}초: {scenario.get('hook_title')}")
        beats = ordered_beats(scenario)
        product_orders = set(product_beat_orders(scenario))
        for captioner in captioners:
            try:
                ref = still(reference_image_prompt(scenario), [], captioner, "ref")
            except Exception as exc:
                note(f"[{hook_type}/{captioner}] 대표 컷 실패: {exc}")
                continue
            out["stills"].append({"type": hook_type, "captioner": captioner, "name": "ref", **ref})
            for i, beat in enumerate(beats, start=1):
                shows = int(beat.get("order") or 0) in product_orders
                use_product = shows and bool(product_refs)
                spec = beat_prompt(scenario, beat, i, len(beats), product=product, shows_product=shows,
                                   has_product_reference=use_product, has_style_reference=not use_product)
                # 컷마다 달라 보이게: 장면 순서마다 촬영 크기를 다르게 배정한다 (4장면이 같은 그림처럼 보였다, 2026-11-27)
                spec += "\nSHOT SIZE: " + (SHOT_PRODUCT if use_product else SHOT_PLAN[(i - 1) % len(SHOT_PLAN)])
                try:
                    st = still(spec, product_refs if use_product else [ref["png"]], captioner, f"beat{i}",
                               style_ref=not use_product)
                    # 영상(MiniMax)용 움직임 묘사: 영어만, 글자를 부르는 말 없이 (Claude)
                    st["motion"] = motion_prompt_for_video(spec) if engine == "flux" else ""
                except Exception as exc:
                    note(f"[{hook_type}/{captioner}] 장면 {i} 실패: {exc}")
                    continue
                out["stills"].append({"type": hook_type, "captioner": captioner, "name": f"beat{i}",
                                      "product": use_product, "spec": spec, **st})
            note(f"[{hook_type}/{captioner}] 스틸컷 {1 + len(beats)}장 완료")
    return out


@app.function(image=image, secrets=[modal.Secret.from_name("napda-backend"), override], cpu=2.0, memory=4096, timeout=1800)
def assemble(scenario: dict, product: dict, clips: dict) -> dict:
    """장면별 클립(이미 만든 것)으로 훅 조립: 나레이션 TTS + 자막 + 소리 맞춤. 영상 모델은 부르지 않는다."""
    import sys as _sys

    if "/app" not in _sys.path:
        _sys.path.insert(0, "/app")
    import copy
    import tempfile

    from app.config import Settings
    from app.genai_provider import GenAIMediaProvider
    from hookpipe.render import render_hook
    from hookpipe.tts import InworldTts, MediaWithTts

    settings = Settings()
    work = Path(tempfile.mkdtemp())
    sc = copy.deepcopy(scenario)
    for beat in sc.get("beats") or []:
        data = clips.get(str(beat.get("order")))
        if data:
            name = f"clip{beat['order']}.mp4"
            (work / name).write_bytes(data)
            beat["prebuilt_clip"] = name
    media = GenAIMediaProvider(settings)
    provider = MediaWithTts(media, InworldTts(settings)) if settings.tts_provider == "inworld" else media
    t = time.time()
    result = render_hook(sc, product, work / "out", provider=provider, settings=settings, tts_enabled=True,
                         resolve_asset=lambda ref: work / ref)
    out_dir = work / "out"
    return {
        "hook_mp4": (out_dir / "hook.mp4").read_bytes(),
        "srt": (out_dir / "hook.srt").read_text(encoding="utf-8") if (out_dir / "hook.srt").exists() else "",
        "seconds": round(time.time() - t, 1),
        "duration": getattr(result, "duration_sec", None),
        "warnings": list(getattr(result, "warnings", []) or []),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("out_dir")
    ap.add_argument("--types", default="B,C")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--captioner", default="claude,gemini", help="FLUX 엔진일 때 장면 묘사 변환기")
    ap.add_argument("--scenario", help="저장된 cycle.json 의 시나리오를 다시 쓴다 (생성 생략)")
    ap.add_argument("--engine", default="flux", choices=["flux", "gemini"], help="스틸컷 이미지 모델")
    ap.add_argument("--same-captions", help="이 cycle.json 의 장면 묘사(이름별)를 그대로 쓴다 (모델 비교용)")
    args = ap.parse_args()

    product = json.loads(Path(args.product).read_text(encoding="utf-8"))
    refs = {Path(p).name: Path(p).read_bytes() for p in args.ref}
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with modal.enable_output(), app.run():
        given = json.loads(Path(args.scenario).read_text(encoding="utf-8"))["scenarios"] if args.scenario else None
        captioners = ["gemini-image"] if args.engine == "gemini" else [c.strip() for c in args.captioner.split(",") if c.strip()]
        fixed = None
        if args.same_captions:
            prev = json.loads(Path(args.same_captions).read_text(encoding="utf-8"))
            fixed = {st["name"]: st["caption"] for st in prev["stills"] if st.get("captioner") == "claude"}
        result = cycle.remote(product, [t.strip().upper() for t in args.types.split(",") if t.strip()], refs,
                              captioners, given, args.engine, fixed)
    for s in result["stills"]:
        data = base64.b64decode(s.pop("png"))
        ext = "jpg" if data.startswith(bytes([0xFF, 0xD8, 0xFF])) else "png"
        (out / f"{s['type']}_{s['captioner']}_{s['name']}.{ext}").write_bytes(data)
    (out / "cycle.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[끝] 시나리오 {len(result['scenarios'])}개, 스틸컷 {len(result['stills'])}장, 전체 {time.time() - t0:.0f}초 → {out}")


if __name__ == "__main__":
    main()
