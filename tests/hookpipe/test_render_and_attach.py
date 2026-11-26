"""hookpipe · 실제 ffmpeg 로 훅 조립과 본편 붙이기를 검증한다 (영상·음성 모델은 대역, 과금 없음)."""

import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from tests.support.hookpipe import FakeMediaProvider, make_video, tools_or_none, worker_scenario
from tests.support.projects_api import fake_google_verifier, login_client
from tests.support.tempdirs import temporary_directory

from fastapi.testclient import TestClient

from app.config import Settings
from app.server import create_app
from hookpipe.body import attach_body
from hookpipe.media import probe
from hookpipe.render import HookRenderError, extract_reference_frames, render_hook

TOOLS = tools_or_none()
PRODUCT = {"name": "60분 비주얼 타이머", "category": "stationery", "verified_facts": ["60분형 아날로그 타이머"]}


def _settings(**overrides: Any) -> SimpleNamespace:
    base = dict(hook_max_sec=20.0, hook_clip_resolution="720p", hook_burn_captions=True,
                hook_max_clip_sec_per_hook=45, video_model="fake-video", tts_model="fake-tts",
                ffmpeg_bin=None, ffprobe_bin=None)
    base.update(overrides)
    return SimpleNamespace(**base)


@unittest.skipUnless(TOOLS, "ffmpeg (testsrc·loudnorm 필터 포함)가 필요합니다")
class RenderHook(unittest.TestCase):
    def test_writes_contract_files_at_contract_spec(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            footage = make_video(TOOLS, root / "upload.mp4", seconds=4.0)
            refs = extract_reference_frames([footage], root / "refs", TOOLS)
            self.assertEqual(len(refs), 2)

            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("B")
            result = render_hook(scenario, PRODUCT, root / "hook", provider=provider, settings=_settings(),
                                 voice="Kore", product_refs=refs, tools=TOOLS)

            out = root / "hook"
            for name in ("hook.mp4", "tts.mp3", "hook.srt", "scenario.json", "render_meta.json",
                         "storyboard_01.png", "storyboard_02.png", "storyboard_03.png"):
                self.assertTrue((out / name).is_file(), name)
            self.assertEqual(json.loads((out / "scenario.json").read_text(encoding="utf-8")), scenario)

            info = probe(TOOLS, out / "hook.mp4")
            self.assertEqual((info.width, info.height), (1080, 1920))
            self.assertTrue(info.has_audio)
            self.assertAlmostEqual(info.duration, 9.0, delta=0.25)
            self.assertAlmostEqual(result.duration_sec, info.duration, places=2)
            self.assertIsNotNone(result.lufs)
            self.assertAlmostEqual(result.lufs, -14.0, delta=2.5)
            self.assertEqual(result.files["storyboard_images"],
                             ["storyboard_01.png", "storyboard_02.png", "storyboard_03.png"])

            # 제품 장면(3번)만 촬영본 컷을 참고로 받고, 나머지는 톤 참고 이미지를 받는다
            self.assertEqual(len(provider.video_calls), 3)
            self.assertEqual([c["duration_sec"] for c in provider.video_calls], [3, 3, 3])
            self.assertEqual(provider.video_calls[2]["reference_paths"], [str(p) for p in refs])
            self.assertTrue(provider.video_calls[0]["reference_paths"][0].endswith("style_ref.png"))
            self.assertEqual({c["voice"] for c in provider.tts_calls}, {"Kore"})
            srt = (out / "hook.srt").read_text(encoding="utf-8")
            self.assertIn("00:00:03,000 --> 00:00:06,000\n두 개는 아가미로", srt)

    def test_long_narration_extends_the_beat_instead_of_cutting_speech(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS, seconds_per_char=0.3)  # 15자 안팎 → 4~5초 음성
            scenario = worker_scenario("B")
            result = render_hook(scenario, PRODUCT, Path(td) / "hook", provider=provider,
                                 settings=_settings(hook_burn_captions=False), tools=TOOLS)
            first = result.beats[0]
            spoken = provider.tts_calls[0]["seconds"]
            self.assertGreater(first["duration"], 3.0)
            self.assertGreaterEqual(first["duration"] + 1e-6, spoken / first["tempo"])
            self.assertLessEqual(first["tempo"], 1.3 + 1e-6)
            self.assertEqual(result.beats[1]["start"], first["duration"])
            self.assertLessEqual(result.duration_sec, 20.3)

    def test_without_tts_makes_a_silent_hook_and_no_tts_file(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS, fail_image=True)
            result = render_hook(worker_scenario("A"), PRODUCT, Path(td) / "hook", provider=provider,
                                 settings=_settings(), tts_enabled=False, tools=TOOLS)
            self.assertEqual(provider.tts_calls, [])
            self.assertIsNone(result.files["tts_audio"])
            self.assertFalse((Path(td) / "hook" / "tts.mp3").exists())
            self.assertTrue(probe(TOOLS, Path(td) / "hook" / "hook.mp4").has_audio)
            # 톤 참고 이미지가 실패해도 클립은 참고 이미지 없이 만들어지고, 경고로 남는다
            self.assertEqual(provider.video_calls[0]["reference_paths"], [])
            self.assertTrue(any("참고 이미지" in w for w in result.warnings))

    def test_stops_before_any_video_call_when_over_the_clip_budget_or_hook_limit(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS)
            with self.assertRaises(HookRenderError):
                render_hook(worker_scenario("B"), PRODUCT, Path(td) / "a", provider=provider,
                            settings=_settings(hook_max_clip_sec_per_hook=8), tools=TOOLS)
            self.assertEqual(provider.video_calls, [])

            too_long = worker_scenario("B")
            too_long["beats"][0]["duration_sec"] = 15.0
            with self.assertRaises(HookRenderError):
                render_hook(too_long, PRODUCT, Path(td) / "b", provider=provider, settings=_settings(), tools=TOOLS)
            self.assertEqual(provider.video_calls, [])
            self.assertEqual(len(provider.tts_calls), 3)  # 첫 시도의 나레이션만, 두 번째는 시작도 하지 않는다


@unittest.skipUnless(TOOLS, "ffmpeg (testsrc·loudnorm 필터 포함)가 필요합니다")
class AttachBody(unittest.TestCase):
    def test_joins_hook_with_portrait_and_silent_landscape_clips(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            hook = make_video(TOOLS, root / "hook.mp4", seconds=3.0, width=1080, height=1920, fps=30)
            (root / "hook.srt").write_text("1\n00:00:00,000 --> 00:00:03,000\n훅 자막\n", encoding="utf-8")
            portrait = make_video(TOOLS, root / "shot1.mp4", seconds=4.0, width=360, height=640)
            landscape = make_video(TOOLS, root / "shot2.mp4", seconds=4.0, width=640, height=360, audio=False)

            result = attach_body(hook, [portrait, landscape], root / "final.mp4", tools=TOOLS, hook_srt=root / "hook.srt")
            info = probe(TOOLS, root / "final.mp4")
            self.assertEqual((info.width, info.height), (1080, 1920))
            self.assertTrue(info.has_audio)
            self.assertAlmostEqual(info.duration, 11.0, delta=0.3)
            self.assertAlmostEqual(result.hook_sec, 3.0, delta=0.15)
            self.assertAlmostEqual(result.body_sec, 8.0, delta=0.25)
            self.assertEqual([s["landscape"] for s in result.segments], [False, True])
            self.assertEqual([s["has_audio"] for s in result.segments], [True, False])
            self.assertTrue((root / "final.srt").is_file())

    def test_body_longer_than_the_limit_is_shortened(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            hook = make_video(TOOLS, root / "hook.mp4", seconds=2.0, width=1080, height=1920, fps=30)
            clips = [make_video(TOOLS, root / f"shot{i}.mp4", seconds=6.0) for i in (1, 2)]
            result = attach_body(hook, clips, root / "final.mp4", tools=TOOLS, limit_sec=6.0)
            self.assertAlmostEqual(result.body_sec, 6.0, delta=0.25)
            self.assertAlmostEqual(result.duration_sec, 8.0, delta=0.3)
            self.assertTrue(any("줄였습니다" in w for w in result.warnings))


def _wait(fetch: Any, done: Any, timeout: float = 120.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        data = fetch()
        if done(data) or time.monotonic() > deadline:
            return data
        time.sleep(0.3)


@unittest.skipUnless(TOOLS, "ffmpeg (testsrc·loudnorm 필터 포함)가 필요합니다")
class ApiFlow(unittest.TestCase):
    """제품 → 작업자 시나리오 → 선택 → 업로드 → 만들기(/renders) → 결과(/deliverables)."""

    def test_render_builds_hook_then_attaches_uploaded_body(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            providers: List[FakeMediaProvider] = []

            def provider_factory(_settings_obj: Any) -> FakeMediaProvider:
                providers.append(FakeMediaProvider(TOOLS))
                return providers[-1]

            def scenario_generator(project: Dict[str, Any], types: List[str], provider: str) -> List[Dict[str, Any]]:
                return [worker_scenario(t, f"sc_{t}_01") for t in types]

            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                google_client_id="dummy-client-id.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            app = create_app(settings=settings, google_token_verifier=fake_google_verifier,
                             scenario_generator=scenario_generator, provider_factory=provider_factory)
            client = TestClient(app)
            login_client(client)

            pid = client.post("/v1/projects", json={"product": PRODUCT, "selected_types": ["B"]}).json()["project_id"]
            scn = client.post(f"/v1/projects/{pid}/scenarios", json={"count": 1})
            self.assertEqual(scn.status_code, 200, scn.text)
            sid = scn.json()["scenarios"][0]["scenario_id"]
            self.assertEqual(client.post(f"/v1/projects/{pid}/scenarios/{sid}/select").status_code, 200)

            footage = make_video(TOOLS, root / "shot1.mp4", seconds=6.0)
            up = client.post(f"/v1/projects/{pid}/uploads/complete",
                             json={"clips": [{"shot_no": 1, "object_key": "uploads/shot1.mp4", "local_path": str(footage)}]})
            self.assertEqual(up.status_code, 200, up.text)

            render = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid})
            self.assertEqual(render.status_code, 202, render.text)
            self.assertEqual(render.json()["selected_type"], "B")

            done = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                         lambda d: d.get("status") in ("QC_READY", "FAILED"))
            self.assertEqual(done["status"], "QC_READY", done)
            video = done["video"]
            self.assertAlmostEqual(video["duration_sec"], 15.0, delta=0.5)  # 훅 9초 + 본편 6초
            self.assertTrue(video["stream_url"] and video["srt_url"])
            self.assertEqual(client.get(f"/v1/projects/{pid}").json()["status"], "DELIVERABLE_READY")

            outputs = client.get(f"/v1/projects/{pid}/outputs").json()["outputs"]
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0]["files"]["hook_video"], "hook.mp4")
            out_dir = Path(outputs[0]["output_dir"])
            self.assertTrue((out_dir / "final.mp4").is_file())
            # 올린 촬영본에서 뽑은 컷이 제품 장면의 참고 이미지로 들어갔다
            self.assertTrue(providers[0].video_calls[2]["reference_paths"][0].endswith("product_ref_01.jpg"))

            # 같은 시나리오로 다시 만들면 훅은 다시 만들지 않고(과금 없음) 본편만 다시 붙인다
            calls_before = sum(len(p.video_calls) for p in providers)
            again = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid})
            self.assertEqual(again.status_code, 202, again.text)
            jid2 = again.json()["job_id"]
            done2 = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                          lambda d: d.get("job_id") == jid2 and d.get("status") in ("QC_READY", "FAILED"))
            self.assertEqual(done2["status"], "QC_READY", done2)
            self.assertEqual(sum(len(p.video_calls) for p in providers), calls_before)
            self.assertEqual(len(client.get(f"/v1/projects/{pid}/outputs").json()["outputs"]), 1)

    def test_hook_endpoint_renders_video_and_failure_is_reported(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            state = {"fail": False}

            class Provider(FakeMediaProvider):
                def generate_video_clip(self, *args: Any, **kwargs: Any) -> None:
                    if state["fail"]:
                        raise RuntimeError("video model quota exceeded")
                    super().generate_video_clip(*args, **kwargs)

            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                google_client_id="dummy-client-id.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            app = create_app(
                settings=settings,
                google_token_verifier=fake_google_verifier,
                scenario_generator=lambda p, types, prov: [worker_scenario(t, f"sc_{t}_01") for t in types],
                provider_factory=lambda _s: Provider(TOOLS),
            )
            client = TestClient(app)
            login_client(client)
            pid = client.post("/v1/projects", json={"product": PRODUCT, "selected_types": ["A"]}).json()["project_id"]
            sid = client.post(f"/v1/projects/{pid}/scenarios", json={"count": 1}).json()["scenarios"][0]["scenario_id"]
            client.post(f"/v1/projects/{pid}/scenarios/{sid}/select")

            hk = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid, "tts": {"enabled": True}})
            self.assertEqual(hk.status_code, 202, hk.text)
            body = client.get(f"/v1/projects/{pid}/hooks/{hk.json()['hook_id']}").json()
            self.assertEqual(body["status"], "done", body)
            self.assertEqual(body["files"]["hook_video"], "hook.mp4")
            self.assertEqual(body["files"]["subtitles_srt"], "hook.srt")
            self.assertTrue((Path(body["output_dir"]) / "hook.mp4").is_file())

            state["fail"] = True
            hk2 = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid})
            failed = client.get(f"/v1/projects/{pid}/hooks/{hk2.json()['hook_id']}").json()
            self.assertEqual(failed["status"], "failed")
            self.assertIn("quota exceeded", failed["error"])
            self.assertIsNone(failed["files"]["hook_video"])


if __name__ == "__main__":
    unittest.main()
