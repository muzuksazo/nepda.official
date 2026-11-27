"""배포 서버에서 영상 파이프라인을 싼 것부터 하나씩 실제로 확인한다. 키는 서버 환경변수에서 읽고 출력하지 않는다.

사용 (서버 컨테이너 안, /app 에서):
    python /app/scripts/hookpipe_smoke.py ready            # 무료: 준비 상태 + 모델 목록 + A 템플릿 목록
    python /app/scripts/hookpipe_smoke.py storage          # 무료에 가까움: R2 에 작은 파일 올리고 내려받기
    python /app/scripts/hookpipe_smoke.py tts --yes        # 유료: 나레이션 1문장
    python /app/scripts/hookpipe_smoke.py image --yes      # 유료: 참고 이미지 1장
    python /app/scripts/hookpipe_smoke.py clip --yes       # 유료: 3초 영상 클립 1개
    python /app/scripts/hookpipe_smoke.py scenario C --yes # 유료(글): 시나리오 1개 (A/B/C)
    python /app/scripts/hookpipe_smoke.py hook <video.mp4> [B|C|A] --yes
                                                           # 유료: 시나리오 → 훅 → 공용 본편 → 붙이기 한 편 (가장 비쌈)
결과 파일은 /tmp/hookpipe_smoke/ 에 남는다. 유료 단계는 --yes 가 없으면 실행하지 않는다.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "backend", ROOT):  # 저장소에서도, 컨테이너(/app)에서도
    if (candidate / "app" / "config.py").is_file() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.config import Settings  # noqa: E402
from app.storage import build_storage  # noqa: E402

OUT = Path("/tmp/hookpipe_smoke") if Path("/tmp").is_dir() else Path.cwd() / "hookpipe_smoke"
PRODUCT = {
    "name": "점검용 제품: 회색 물기제거 스펀지",
    "category": "living",
    "verified_facts": ["회색 직사각형 스펀지로, 한 손에 쥐어지는 크기다", "흐르는 물에 적신 뒤 손으로 꾹 짜서 쓴다",
                       "세면대·욕조 가장자리에 남은 물기를 문질러 닦아 낸다"],
}


def paid(args: list) -> None:
    if "--yes" not in args:
        print("유료 호출입니다. 실행하려면 --yes 를 붙이세요.")
        raise SystemExit(2)


def timed(label: str, fn):
    started = time.monotonic()
    try:
        result = fn()
        print(f"OK   {label}  {time.monotonic() - started:.1f}초")
        return result
    except Exception as exc:
        print(f"FAIL {label}  {time.monotonic() - started:.1f}초  {type(exc).__name__}: {str(exc)[:400]}")
        raise SystemExit(1)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    settings = Settings()
    storage = build_storage(settings)
    OUT.mkdir(parents=True, exist_ok=True)
    step = args[0]

    if step == "ready":
        from hookpipe import readiness

        report = readiness.check(settings, storage, deep=True)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ready"] else 1

    if step == "storage":
        # 저장소(R2) 연결: 작은 파일을 올리고, 서명 주소를 만들고, 다시 내려받는다 (요금은 사실상 없음)
        probe_file = OUT / "storage_probe.txt"
        probe_file.write_text(f"napda storage probe {time.time()}", encoding="utf-8")
        key = "healthcheck/storage_probe.txt"
        url = timed(f"올리기 ({settings.storage_backend})", lambda: storage.upload_file(probe_file, key))
        print(f"     주소: {str(url).split('?', 1)[0][:80]} (서명 부분은 표시하지 않음)")
        back = OUT / "storage_probe_back.txt"
        timed("내려받기", lambda: storage.download_file(key, back))
        same = back.read_text(encoding="utf-8") == probe_file.read_text(encoding="utf-8")
        print(("OK   " if same else "FAIL ") + "내용 일치")
        from hookpipe.a_templates import TemplateError, load_catalog

        try:
            catalog = load_catalog(settings, storage, OUT)
            print(f"OK   A 템플릿 {len(catalog['templates'])}개 ({catalog['location']})")
        except TemplateError as exc:
            print(f"--   A 템플릿 없음: {exc}  (A 는 실시간 생성으로 갑니다)")
        return 0 if same else 1

    from hookpipe.service import HookPipeline

    pipeline = HookPipeline(settings, None, None, storage)
    if step == "tts":
        paid(args)
        provider = pipeline._provider()
        ext = getattr(provider, "tts_extension", ".wav")
        target = OUT / f"tts{ext}"
        timed("나레이션 1문장", lambda: provider.generate_tts_beat("세수하고 나면 세면대 물기가 늘 남습니다.", target,
                                                              voice_name=settings.tts_default_voice))
        print(f"     → {target}")
        return 0
    if step == "image":
        paid(args)
        target = OUT / "image.jpg"
        timed("참고 이미지 1장", lambda: pipeline._provider().generate_reference_image(
            "A small clay humpback whale in a soft diorama, vertical 9:16, no text.", target, aspect_ratio="9:16",
            mime_type="image/jpeg", skip_existing=False))
        print(f"     → {target}")
        return 0
    if step == "clip":
        paid(args)
        from hookpipe.render import generate_clip_with_retries

        target = OUT / "clip.mp4"
        tag = timed("영상 클립 3초", lambda: generate_clip_with_retries(
            pipeline._provider(), "A hand wipes water off the edge of a white bathroom sink with a grey sponge. "
            "Realistic smartphone footage, vertical 9:16, no text.", target, clip_sec=3,
            resolution=settings.hook_clip_resolution, reference_paths=[]))
        print(f"     → {target}  (재시도: {tag[0] or '없음'})")
        return 0
    if step == "scenario":
        paid(args)
        from hookpipe.workers import generate_with_worker, template_or_realtime_a, WORKERS

        hook_type = (args[1] if len(args) > 1 and not args[1].startswith("--") else "C").upper()
        workers = dict(WORKERS)
        workers["A"] = template_or_realtime_a(storage, WORKERS["A"])
        project = {"project_id": "proj_smoke01", "product": PRODUCT}
        items = timed(f"{hook_type} 시나리오", lambda: generate_with_worker(
            hook_type, project, settings, round_no=1, previous_scenarios=[], workers=workers))
        (OUT / f"scenario_{hook_type}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        s = items[0]
        print(f"     {s['hook_title']} · {s['hook_duration_sec']}초 · 장면 {len(s['beats'])}개 · 위반 {s['ad_spec'].get('rule_violations')}")
        return 0
    if step == "hook":
        paid(args)
        video = Path(args[1]) if len(args) > 1 else None
        if not video or not video.is_file():
            print("촬영 영상 파일 경로를 주세요: hook <video.mp4> [B|C|A] --yes")
            return 1
        hook_type = (args[2] if len(args) > 2 and not args[2].startswith("--") else "C").upper()
        return _full(settings, video, hook_type)
    print(__doc__)
    return 1


def _full(settings: Settings, video: Path, hook_type: str) -> int:
    """API 흐름 그대로 한 편: 프로젝트 → 시나리오 → 선택 → 업로드 → /renders → /deliverables."""
    from fastapi.testclient import TestClient

    from app.auth import AuthenticatedUser
    from app.server import create_app

    work = OUT / "full"
    settings = settings.model_copy(update={"daily_render_limit": 50, "db_path": str(work / "smoke.db"),
                                           "work_root": str(work / "work"), "output_dir": str(work / "outputs")})
    app = create_app(settings=settings, google_token_verifier=lambda cred, cid: AuthenticatedUser(
        user_id="smoke-user", email="smoke@example.com", name="점검", picture=None))
    client = TestClient(app)
    assert client.post("/v1/auth/google", json={"credential": "smoke"}).status_code == 200
    pid = client.post("/v1/projects", json={"product": PRODUCT, "selected_types": [hook_type]}).json()["project_id"]
    scn = timed(f"{hook_type} 시나리오", lambda: client.post(f"/v1/projects/{pid}/scenarios", json={"count": 1}))
    if scn.status_code != 200:
        print(scn.text[:600])
        return 1
    sid = scn.json()["scenarios"][0]["scenario_id"]
    client.post(f"/v1/projects/{pid}/scenarios/{sid}/select")
    up = client.post(f"/v1/projects/{pid}/uploads/complete",
                     json={"clips": [{"shot_no": 1, "object_key": f"smoke/{video.name}", "local_path": str(video)}]})
    if up.status_code != 200:
        print(up.text[:600])
        return 1
    jid = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid}).json()["job_id"]
    started, last = time.monotonic(), None
    while True:
        job = client.get(f"/v1/projects/{pid}").json().get("latest_job") or {}
        stage = (job.get("status"), job.get("stage"))
        if stage != last:
            print(f"     {time.monotonic() - started:5.0f}초  {stage[0]}  {stage[1]}")
            last = stage
        if job.get("status") in ("QC_READY", "FAILED"):
            break
        time.sleep(3)
    done = client.get(f"/v1/projects/{pid}/deliverables").json()
    print(json.dumps({"status": done.get("status"), "video": done.get("video"), "error": job.get("error"),
                      "warnings": (job.get("artifacts") or {}).get("warnings")}, ensure_ascii=False, indent=2))
    print(f"     작업 폴더: {work}")
    return 0 if done.get("status") == "QC_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
