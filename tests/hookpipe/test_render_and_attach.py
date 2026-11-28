"""hookpipe · 실제 ffmpeg 로 훅 조립과 본편 붙이기를 검증한다 (영상·음성 모델은 대역, 과금 없음)."""

import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from tests.support.hookpipe import FakeMediaProvider, fake_body_writer, make_video, tools_or_none, worker_scenario
from tests.support.projects_api import fake_google_verifier, login_client
from tests.support.tempdirs import temporary_directory

from fastapi.testclient import TestClient

from app.config import Settings
from app.server import create_app
from hookpipe.body import attach_body
from hookpipe.body_edit import make_body
from hookpipe.captions import parse_srt
from hookpipe.media import probe, run_ffmpeg
from hookpipe.render import HookRenderError, extract_reference_frames, render_hook
from hookpipe.service import HookPipeline

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
            self.assertTrue(Path(provider.video_calls[0]["reference_paths"][0]).name.startswith("style_"))
            self.assertTrue(Path(provider.video_calls[0]["reference_paths"][0]).name.endswith("_ref.jpg"))
            self.assertTrue(result.captions_burned)
            self.assertEqual({c["voice"] for c in provider.tts_calls}, {"Kore"})
            srt = (out / "hook.srt").read_text(encoding="utf-8")
            self.assertIn("00:00:03,000 --> 00:00:06,000\n두 개는 아가미로", srt)

    def _layout_image(self, workers: Path) -> Path:
        layout = workers / "c" / "blockouts" / "desk.png"
        layout.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(TOOLS, ["-f", "lavfi", "-i", "color=c=gray:s=360x640", "-frames:v", "1", str(layout)])
        return layout

    def test_layout_reference_becomes_the_first_frame_of_that_beat(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            layout = self._layout_image(root / "workers")
            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("B")
            scenario["beats"][0]["first_frame_ref"] = "c/blockouts/desk.png"
            scenario["beats"][0]["first_frame_prompt"] = "make this blockout photorealistic"
            settings = _settings(hook_workers_dir=str(root / "workers"), image_model="fake-image")
            result = render_hook(scenario, PRODUCT, root / "hook", provider=provider, settings=settings, tools=TOOLS)

            # 이미지 모델이 구도 참고 이미지를 받아 첫 프레임을 만들고, 그 장면의 클립만 그 화면에서 시작한다
            refined = [c for c in provider.image_calls if c.get("anchor_paths")]
            self.assertEqual(len(refined), 1)
            self.assertEqual(refined[0]["prompt"], "make this blockout photorealistic")
            self.assertEqual([str(p) for p in refined[0]["anchor_paths"]], [str(layout.resolve())])
            first, second = provider.video_calls[0], provider.video_calls[1]
            self.assertTrue(Path(first["first_frame_path"]).name.startswith("first_"))
            self.assertEqual(first["reference_paths"], [])
            self.assertIn("starts from the provided first frame", first["prompt"])
            self.assertIsNone(second["first_frame_path"])
            self.assertTrue(Path(second["reference_paths"][0]).name.startswith("style_"))
            self.assertFalse([w for w in result.warnings if "구도 참고" in w or "첫 프레임" in w])
            self.assertTrue((root / "hook" / "hook.mp4").is_file())

            # 같은 캐시로 다시 만들면 첫 프레임 이미지와 클립을 다시 사지 않는다
            images, clips = len(provider.image_calls), len(provider.video_calls)
            render_hook(scenario, PRODUCT, root / "hook2", provider=provider, settings=settings, tools=TOOLS,
                        cache_dir=root / "hook" / "_work" / "cache")
            self.assertEqual((len(provider.image_calls), len(provider.video_calls)), (images, clips))

    def test_layout_reference_can_be_used_without_refining(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            self._layout_image(root / "workers")
            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("B")
            scenario["beats"][0].update({"first_frame_ref": "c/blockouts/desk.png", "first_frame_refine": False})
            render_hook(scenario, PRODUCT, root / "hook", provider=provider,
                        settings=_settings(hook_workers_dir=str(root / "workers")), tools=TOOLS)
            self.assertFalse([c for c in provider.image_calls if c.get("anchor_paths")])
            self.assertTrue(Path(provider.video_calls[0]["first_frame_path"]).name.startswith("desk"))

    def test_missing_or_escaping_layout_reference_falls_back_with_a_warning(self) -> None:
        for ref in ("c/blockouts/nope.png", "../outside.png"):
            with temporary_directory() as td:
                root = Path(td)
                self._layout_image(root / "workers")
                run_ffmpeg(TOOLS, ["-f", "lavfi", "-i", "color=c=gray:s=360x640", "-frames:v", "1", str(root / "outside.png")])
                provider = FakeMediaProvider(TOOLS)
                scenario = worker_scenario("B")
                scenario["beats"][0]["first_frame_ref"] = ref
                result = render_hook(scenario, PRODUCT, root / "hook", provider=provider,
                                     settings=_settings(hook_workers_dir=str(root / "workers")), tools=TOOLS)
                self.assertIsNone(provider.video_calls[0]["first_frame_path"], ref)
                self.assertTrue([w for w in result.warnings if "구도 참고 이미지를 찾지 못해" in w], ref)
                self.assertTrue((root / "hook" / "hook.mp4").is_file())

    def test_failed_first_frame_image_falls_back_to_the_plain_clip(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            self._layout_image(root / "workers")
            provider = FakeMediaProvider(TOOLS, fail_image=True)
            scenario = worker_scenario("B")
            scenario["beats"][0]["first_frame_ref"] = "c/blockouts/desk.png"
            result = render_hook(scenario, PRODUCT, root / "hook", provider=provider,
                                 settings=_settings(hook_workers_dir=str(root / "workers")), tools=TOOLS)
            self.assertIsNone(provider.video_calls[0]["first_frame_path"])
            self.assertTrue([w for w in result.warnings if "첫 프레임 이미지를 만들지 못해" in w])
            self.assertTrue((root / "hook" / "hook.mp4").is_file())

    def test_prebuilt_clip_wins_over_layout_reference_and_says_so(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            self._layout_image(root / "workers")
            assets = root / "assets"
            make_video(TOOLS, assets / "sh" / "clip1.mp4", seconds=3.0, audio=False)
            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("B")
            # 자체 모델 엔진처럼 장면에 미리 만든 클립이 들어온 경우: 그 클립을 쓰고 구도 참고는 건너뛴다
            scenario["beats"][0].update({"first_frame_ref": "c/blockouts/desk.png", "prebuilt_clip": "sh/clip1.mp4"})
            result = render_hook(
                scenario, PRODUCT, root / "hook", provider=provider,
                settings=_settings(hook_workers_dir=str(root / "workers")), tools=TOOLS,
                resolve_asset=lambda ref: (assets / ref) if (assets / ref).is_file() else None,
            )
            self.assertFalse([c for c in provider.image_calls if c.get("anchor_paths")])  # 첫 프레임 이미지를 사지 않는다
            self.assertEqual(len(provider.video_calls), 2)  # 미리 만든 장면은 영상 모델을 부르지 않는다
            self.assertTrue(all(c["first_frame_path"] is None for c in provider.video_calls))
            self.assertTrue([w for w in result.warnings if "미리 만든 영상을 써서 구도 참고 이미지를 쓰지 않았습니다" in w])
            self.assertTrue((root / "hook" / "hook.mp4").is_file())

    def test_storyboard_still_is_the_first_frame_as_is(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            self._layout_image(root / "workers")
            stills = {}
            for order in (1, 2, 3):
                stills[order] = root / "stills" / f"still{order}.png"
                stills[order].parent.mkdir(parents=True, exist_ok=True)
                run_ffmpeg(TOOLS, ["-f", "lavfi", "-i", "color=c=blue:s=360x640", "-frames:v", "1", str(stills[order])])
            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("B")
            scenario["beats"][0]["first_frame_ref"] = "c/blockouts/desk.png"  # 콘티 스틸컷이 구도 참고보다 우선
            result = render_hook(scenario, PRODUCT, root / "hook", provider=provider,
                                 settings=_settings(hook_workers_dir=str(root / "workers")), tools=TOOLS,
                                 storyboard_stills=stills)
            # 스틸컷은 이미 실사라 이미지 모델로 고치지 않고, 톤 참고 이미지도 사지 않는다
            self.assertEqual(provider.image_calls, [])
            self.assertEqual(len(provider.video_calls), 3)
            for call in provider.video_calls:
                self.assertTrue(Path(call["first_frame_path"]).name.startswith("still"))
                self.assertIn("starts from the provided first frame", call["prompt"])
            self.assertEqual(provider.video_calls[0]["reference_paths"], [])
            self.assertTrue((root / "hook" / "hook.mp4").is_file())
            self.assertFalse([w for w in result.warnings if "구도 참고" in w])

    def test_storyboard_still_is_skipped_for_prebuilt_beats(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            assets = root / "assets"
            make_video(TOOLS, assets / "sh" / "clip1.mp4", seconds=3.0, audio=False)
            still = root / "still1.png"
            run_ffmpeg(TOOLS, ["-f", "lavfi", "-i", "color=c=blue:s=360x640", "-frames:v", "1", str(still)])
            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("B")
            scenario["beats"][0]["prebuilt_clip"] = "sh/clip1.mp4"
            render_hook(scenario, PRODUCT, root / "hook", provider=provider, settings=_settings(), tools=TOOLS,
                        resolve_asset=lambda ref: (assets / ref) if (assets / ref).is_file() else None,
                        storyboard_stills={1: still})
            self.assertEqual(len(provider.video_calls), 2)
            self.assertTrue(all(c["first_frame_path"] is None for c in provider.video_calls))

    def test_long_narration_extends_the_beat_instead_of_cutting_speech(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS, seconds_per_char=0.3)  # 15자 안팎 → 4~5초 음성
            scenario = worker_scenario("B")
            result = render_hook(scenario, PRODUCT, Path(td) / "hook", provider=provider,
                                 settings=_settings(hook_burn_captions=False), tools=TOOLS)
            first = result.beats[0]
            spoken = next(c["seconds"] for c in provider.tts_calls if c["text"] == scenario["beats"][0]["narration"])
            self.assertGreater(first["duration"], 3.0)
            self.assertGreaterEqual(first["duration"] + 1e-6, spoken / first["tempo"])
            self.assertLessEqual(first["tempo"], 1.3 + 1e-6)
            self.assertEqual(result.beats[1]["start"], first["duration"])
            self.assertLessEqual(result.duration_sec, 20.3)

    def test_narration_far_longer_than_the_hook_limit_keeps_as_much_speech_as_fits(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS, seconds_per_char=0.9)  # 장면마다 13~16초짜리 음성
            result = render_hook(worker_scenario("B"), PRODUCT, Path(td) / "hook", provider=provider,
                                 settings=_settings(hook_burn_captions=False), tools=TOOLS)
            # 상한 20초를 꽉 채워 쓰고(시나리오 길이 9초로 되돌아가지 않는다), 잘리는 장면을 경고로 알린다
            self.assertAlmostEqual(result.duration_sec, 20.0, delta=0.3)
            self.assertTrue(all(b["duration"] >= 3.0 for b in result.beats))
            self.assertTrue(all(abs(b["tempo"] - 1.6) < 1e-6 for b in result.beats))
            self.assertTrue(any("나레이션 끝이 잘립니다" in w for w in result.warnings), result.warnings)

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

            too_long = worker_scenario("B")
            too_long["beats"][0]["duration_sec"] = 15.0
            with self.assertRaises(HookRenderError):
                render_hook(too_long, PRODUCT, Path(td) / "b", provider=provider, settings=_settings(), tools=TOOLS)

            # 1초 장면도 클립은 최소 3초로 요청된다: 1초 x 10장면 = 30초 요청 → 상한 20초에 걸린다
            many = worker_scenario("B")
            many["beats"] = [dict(many["beats"][0], order=i + 1, duration_sec=1.0) for i in range(10)]
            with self.assertRaises(HookRenderError):
                render_hook(many, PRODUCT, Path(td) / "c", provider=provider,
                            settings=_settings(hook_max_clip_sec_per_hook=20), tools=TOOLS)

            duplicated = worker_scenario("B")
            duplicated["beats"][1]["order"] = 1
            with self.assertRaises(HookRenderError):
                render_hook(duplicated, PRODUCT, Path(td) / "d", provider=provider, settings=_settings(), tools=TOOLS)

            # 넷 모두 과금 호출(나레이션·참고 이미지·클립)을 하나도 하지 않고 멈춘다
            self.assertEqual((provider.tts_calls, provider.image_calls, provider.video_calls), ([], [], []))

    def test_sub_second_silent_beat_freezes_the_previous_shot_instead_of_buying_a_clip(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS)
            scenario = worker_scenario("A")
            scenario["ad_spec"] = {"track_archetype": "A_bgrade_reversal"}
            scenario["beats"] = [
                dict(scenario["beats"][0], order=1, duration_sec=3.0),
                dict(scenario["beats"][1], order=2, duration_sec=3.0),
                {"order": 3, "role": "패턴 인터럽트", "duration_sec": 0.3, "visual": "화면 전체가 정지", "narration": "", "caption": "……"},
                dict(scenario["beats"][2], order=4, duration_sec=4.0),
            ]
            result = render_hook(scenario, PRODUCT, Path(td) / "hook", provider=provider, settings=_settings(),
                                 tools=TOOLS)
            self.assertEqual([c["duration_sec"] for c in provider.video_calls], [3, 3, 4])  # 0.3초 장면은 요청하지 않는다
            self.assertEqual([b["hold"] for b in result.beats], [False, False, True, False])
            self.assertAlmostEqual(probe(TOOLS, Path(td) / "hook" / "hook.mp4").duration, 10.3, delta=0.25)
            self.assertAlmostEqual(result.beats[3]["start"], 6.3, places=2)
            self.assertEqual(len(result.files["storyboard_images"]), 4)

    def test_prebuilt_clips_replace_model_calls_and_a_missing_file_stops_before_paying(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            assets = root / "assets"
            make_video(TOOLS, assets / "a" / "physics_01.mp4", seconds=3.0, audio=False)
            make_video(TOOLS, assets / "a" / "physics_02.mp4", seconds=3.0, audio=False)
            (root / "outside.mp4").write_bytes((assets / "a" / "physics_01.mp4").read_bytes())
            pipeline = HookPipeline(
                SimpleNamespace(hook_assets_dir=str(assets), output_dir=str(root / "out")), None, None,
                SimpleNamespace(download_file=lambda key, dest: (_ for _ in ()).throw(FileNotFoundError(key))),
            )
            resolve = lambda ref: pipeline.resolve_asset(ref, root / "work")  # noqa: E731

            # 앞의 두 장면은 미리 만든 영상, 마지막 제품 장면만 영상 모델로 만든다
            scenario = worker_scenario("A")
            scenario["ad_spec"] = {"track_archetype": "A_bgrade_reversal"}
            scenario["beats"][0]["prebuilt_clip"] = "a/physics_01.mp4"
            scenario["beats"][1]["prebuilt_clip"] = "a/physics_02.mp4"
            provider = FakeMediaProvider(TOOLS)
            result = render_hook(scenario, PRODUCT, root / "hook", provider=provider, settings=_settings(),
                                 tools=TOOLS, resolve_asset=resolve)
            self.assertEqual([c["duration_sec"] for c in provider.video_calls], [3])
            self.assertEqual([b["prebuilt"] for b in result.beats], [True, True, False])
            self.assertAlmostEqual(probe(TOOLS, root / "hook" / "hook.mp4").duration, 9.0, delta=0.25)

            # 파일이 없거나, 소재 폴더 밖을 가리키면 아무것도 사지 않고 멈춘다
            for bad in ("a/missing.mp4", "../outside.mp4", str(root / "outside.mp4")):
                broken = worker_scenario("A")
                broken["beats"][0]["prebuilt_clip"] = bad
                fresh = FakeMediaProvider(TOOLS)
                with self.assertRaises(HookRenderError):
                    render_hook(broken, PRODUCT, root / "bad", provider=fresh, settings=_settings(),
                                tools=TOOLS, resolve_asset=resolve)
                self.assertEqual((fresh.tts_calls, fresh.image_calls, fresh.video_calls), ([], [], []), bad)

    def test_clip_rejected_with_reference_is_retried_once_without_it(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS)
            real_clip = provider.generate_video_clip

            def picky(prompt: str, out_path: Any, **kwargs: Any) -> None:
                if kwargs.get("reference_paths"):
                    provider.video_calls.append({"rejected": True, **kwargs})
                    raise RuntimeError("ended with status='failed', errors=[Error(code='INVALID_ARGUMENT')]")
                real_clip(prompt, out_path, **kwargs)

            provider.generate_video_clip = picky  # type: ignore[method-assign]
            result = render_hook(worker_scenario("A"), PRODUCT, Path(td) / "hook", provider=provider,
                                 settings=_settings(), tools=TOOLS)
            self.assertTrue(all("retried_without_reference" in b["reused"] for b in result.beats))

            # 참고 이미지 없이도 거절되는 단면 장면은 바깥에서 본 장면으로 바꿔 한 번 더 보낸다
            fresh = FakeMediaProvider(TOOLS)
            plain = fresh.generate_video_clip

            def no_cross_sections(prompt: str, out_path: Any, **kwargs: Any) -> None:
                if "단면" in prompt:
                    fresh.video_calls.append({"rejected": True})
                    raise RuntimeError("errors=[Error(code='INVALID_ARGUMENT')]")
                plain(prompt, out_path, **kwargs)

            fresh.generate_video_clip = no_cross_sections  # type: ignore[method-assign]
            cut = worker_scenario("B")
            cut["beats"][1]["visual"] = "심장 세 개가 뛰는 단면 시각화"
            again = render_hook(cut, PRODUCT, Path(td) / "cut", provider=fresh, settings=_settings(), tools=TOOLS)
            self.assertIn("retried_outside_view", again.beats[1]["reused"])
            self.assertNotIn("단면", again.beats[1]["prompt"])
            self.assertEqual(sum(1 for c in fresh.video_calls if c.get("rejected")), 2)
            self.assertEqual(sum(1 for c in provider.video_calls if c.get("rejected")), 3)
            self.assertTrue(any("참고 이미지 없이" in w for w in result.warnings))
            # 참고 이미지는 긴 변 1280 이하 JPEG 으로 다시 저장해서 보낸다
            sent = [c["reference_paths"][0] for c in provider.video_calls if c.get("rejected")]
            self.assertTrue(all(Path(p).name.endswith("_ref.jpg") for p in sent), sent)

    def test_rerender_buys_only_what_changed(self) -> None:
        with temporary_directory() as td:
            provider = FakeMediaProvider(TOOLS)
            cache = Path(td) / "cache"
            scenario = worker_scenario("B")
            render_hook(scenario, PRODUCT, Path(td) / "first", provider=provider, settings=_settings(),
                        tools=TOOLS, cache_dir=cache)
            counts = (len(provider.tts_calls), len(provider.image_calls), len(provider.video_calls))
            self.assertEqual(counts, (3, 1, 3))

            # 같은 내용으로 다른 폴더에 다시: 새로 사는 것이 없다
            again = render_hook(scenario, PRODUCT, Path(td) / "second", provider=provider, settings=_settings(),
                                tools=TOOLS, cache_dir=cache)
            self.assertEqual((len(provider.tts_calls), len(provider.image_calls), len(provider.video_calls)), counts)
            self.assertEqual(again.beats[0]["reused"], ["tts", "clip"])
            self.assertTrue((Path(td) / "second" / "hook.mp4").is_file())

            # 둘째 장면의 나레이션과 화면만 바꾸면 그 장면의 음성과 클립만 새로 산다
            changed = worker_scenario("B")
            changed["beats"][1]["narration"] = "나머지 하나가 온몸으로 보냅니다."
            changed["beats"][1]["visual"] = "큰 심장 하나가 천천히 뛴다"
            render_hook(changed, PRODUCT, Path(td) / "third", provider=provider, settings=_settings(),
                        tools=TOOLS, cache_dir=cache)
            self.assertEqual((len(provider.tts_calls), len(provider.image_calls), len(provider.video_calls)), (4, 1, 4))
            self.assertEqual(provider.tts_calls[-1]["text"], "나머지 하나가 온몸으로 보냅니다.")

            # 나레이션을 끄고 같은 폴더에 다시 만들면 예전 tts.mp3 가 남지 않는다
            silent = render_hook(scenario, PRODUCT, Path(td) / "first", provider=provider, settings=_settings(),
                                 tts_enabled=False, tools=TOOLS, cache_dir=cache)
            self.assertIsNone(silent.files["tts_audio"])
            self.assertFalse((Path(td) / "first" / "tts.mp3").exists())


@unittest.skipUnless(TOOLS, "ffmpeg (testsrc·loudnorm 필터 포함)가 필요합니다")
class SharedBody(unittest.TestCase):
    def test_body_is_exactly_ten_seconds_with_narration_captions_and_reused(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            clips = [make_video(TOOLS, root / "a.mp4", seconds=6.0, width=360, height=640),
                     make_video(TOOLS, root / "b.mp4", seconds=3.0, width=640, height=360, audio=False)]
            provider = FakeMediaProvider(TOOLS)
            settings = _settings(body_target_sec=10.0)
            prompts: List[str] = []

            def writer(prompt: str, frames: Any) -> Dict[str, Any]:
                prompts.append(prompt)
                self.assertEqual(len(frames), 10)  # 클립마다 5장
                return fake_body_writer(prompt, frames)

            made = make_body(clips, PRODUCT, root / "body", provider=provider, settings=settings, tools=TOOLS,
                             writer=writer)
            info = probe(TOOLS, made.video)
            self.assertEqual((info.width, info.height), (1080, 1920))
            self.assertAlmostEqual(info.duration, 10.0, delta=0.15)
            self.assertTrue(info.has_audio)
            self.assertAlmostEqual(made.lufs, -14.0, delta=2.5)
            self.assertEqual(len(provider.tts_calls), 2)
            srt = made.srt.read_text(encoding="utf-8")
            self.assertIn("한 손에 쥐는", srt)
            self.assertIn("60분 비주얼 타이머", prompts[0])  # 제품 사실만으로 대본을 쓴다
            self.assertEqual(provider.video_calls, [])  # 본편은 영상 모델을 쓰지 않는다

            again = make_body(clips, PRODUCT, root / "body", provider=provider, settings=settings, tools=TOOLS,
                              writer=writer)
            self.assertTrue(again.reused)
            self.assertEqual((len(prompts), len(provider.tts_calls)), (1, 2))

    def test_b_and_c_hooks_of_one_project_share_one_body(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            provider = FakeMediaProvider(TOOLS)
            calls: List[int] = []

            def counting_writer(prompt: str, frames: Any) -> Dict[str, Any]:
                calls.append(1)
                return fake_body_writer(prompt, frames)

            settings = Settings(
                _env_file=None, gemini_api_key="dummy-key", google_client_id="dummy.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
        tts_provider="gemini",  # 나레이션은 대역 공급자로 (기본값 inworld 는 실제 키가 필요)
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"), db_path=str(root / "napda.db"), daily_render_limit=10,
            )
            app = create_app(settings=settings, google_token_verifier=fake_google_verifier,
                             scenario_generator=lambda p, types, prov: [worker_scenario(t, f"sc_{t}_01") for t in types],
                             provider_factory=lambda _s: provider, body_writer=counting_writer)
            client = TestClient(app)
            login_client(client)
            app.state.project_store.refund_wallet_credits("seller-1", 100)
            pid = client.post("/v1/projects", json={"product": PRODUCT, "selected_types": ["B", "C"]}).json()["project_id"]
            scenarios = client.post(f"/v1/projects/{pid}/scenarios", json={"count": 1}).json()["scenarios"]
            footage = make_video(TOOLS, root / "shot.mp4", seconds=6.0)
            client.post(f"/v1/projects/{pid}/uploads/complete",
                        json={"clips": [{"shot_no": 1, "object_key": "uploads/shot.mp4", "local_path": str(footage)}]})
            durations = []
            for scenario in scenarios:
                sid = scenario["scenario_id"]
                client.post(f"/v1/projects/{pid}/scenarios/{sid}/select")
                jid = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid}).json()["job_id"]
                done = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                             lambda d: d.get("job_id") == jid and d.get("status") in ("QC_READY", "FAILED"))
                self.assertEqual(done["status"], "QC_READY", done)
                durations.append(done["video"]["duration_sec"])
            self.assertEqual(len(calls), 1)  # 본편 대본은 한 번만 만들었다 (B·C 공용)
            self.assertTrue(all(abs(d - 19.0) < 0.5 for d in durations), durations)


@unittest.skipUnless(TOOLS, "ffmpeg (testsrc·loudnorm 필터 포함)가 필요합니다")
class AttachBody(unittest.TestCase):
    def test_joins_hook_with_portrait_and_silent_landscape_clips(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            hook = make_video(TOOLS, root / "hook.mp4", seconds=3.0, width=1080, height=1920, fps=30)
            (root / "hook.srt").write_text("1\n00:00:00,000 --> 00:00:03,000\n훅 자막\n", encoding="utf-8")
            portrait = make_video(TOOLS, root / "shot1.mp4", seconds=4.0, width=360, height=640)
            landscape = make_video(TOOLS, root / "shot2.mp4", seconds=4.0, width=640, height=360, audio=False)

            (root / "body.srt").write_text("1\n00:00:01,000 --> 00:00:02,500\n본편 자막\n\n2\n00:00:30,000 --> 00:00:31,000\n잘린 뒤 자막\n",
                                           encoding="utf-8")
            result = attach_body(hook, [portrait, landscape], root / "final.mp4", tools=TOOLS,
                                 hook_srt=root / "hook.srt", body_srt=root / "body.srt")
            info = probe(TOOLS, root / "final.mp4")
            self.assertEqual((info.width, info.height), (1080, 1920))
            self.assertTrue(info.has_audio)
            self.assertAlmostEqual(info.duration, 11.0, delta=0.3)
            self.assertAlmostEqual(result.hook_sec, 3.0, delta=0.15)
            self.assertAlmostEqual(result.body_sec, 8.0, delta=0.25)
            self.assertEqual([s["landscape"] for s in result.segments], [False, True])
            self.assertEqual([s["has_audio"] for s in result.segments], [True, False])
            final_srt = (root / "final.srt").read_text(encoding="utf-8")
            self.assertIn("훅 자막", final_srt)
            self.assertIn("본편 자막", final_srt)
            self.assertNotIn("잘린 뒤 자막", final_srt)  # 본편 길이(8초)를 넘는 자막은 버린다
            body_cue = [c for c in parse_srt(final_srt) if c[2] == "본편 자막"][0]
            self.assertAlmostEqual(body_cue[0], result.hook_sec + 1.0, delta=0.01)

    def test_body_longer_than_the_limit_is_shortened(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            hook = make_video(TOOLS, root / "hook.mp4", seconds=2.0, width=1080, height=1920, fps=30)
            clips = [make_video(TOOLS, root / f"shot{i}.mp4", seconds=6.0) for i in (1, 2)]
            result = attach_body(hook, clips, root / "final.mp4", tools=TOOLS, limit_sec=6.0)
            self.assertAlmostEqual(result.body_sec, 6.0, delta=0.25)
            self.assertAlmostEqual(result.duration_sec, 8.0, delta=0.3)
            self.assertTrue(any("줄였습니다" in w for w in result.warnings))


def _client(root: Path, provider: Any, *, scenario_generator: Any = None, **overrides: Any) -> TestClient:
    settings = Settings(
        _env_file=None,
        gemini_api_key="dummy-key",
        google_client_id="dummy-client-id.apps.googleusercontent.com",
        session_secret="test-session-secret-32bytes-minimum",
        tts_provider="gemini",  # 나레이션은 대역 공급자로 (기본값 inworld 는 실제 키가 필요)
        work_root=str(root / "work"),
        output_dir=str(root / "outputs"),
        db_path=str(root / "napda.db"),
        **overrides,
    )
    root.mkdir(parents=True, exist_ok=True)
    app = create_app(
        settings=settings,
        google_token_verifier=fake_google_verifier,
        scenario_generator=scenario_generator
        or (lambda p, types, prov: [worker_scenario(t, f"sc_{t}_01") for t in types]),
        provider_factory=lambda _s: provider,
        body_writer=fake_body_writer,
    )
    client = TestClient(app)
    login_client(client)
    app.state.project_store.refund_wallet_credits("seller-1", 100)
    return client


def _project_with_selected_scenario(client: TestClient, hook_type: str) -> Any:
    pid = client.post("/v1/projects", json={"product": PRODUCT, "selected_types": [hook_type]}).json()["project_id"]
    sid = client.post(f"/v1/projects/{pid}/scenarios", json={"count": 1}).json()["scenarios"][0]["scenario_id"]
    assert client.post(f"/v1/projects/{pid}/scenarios/{sid}/select").status_code == 200
    return pid, sid


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
        tts_provider="gemini",  # 나레이션은 대역 공급자로 (기본값 inworld 는 실제 키가 필요)
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            app = create_app(settings=settings, google_token_verifier=fake_google_verifier,
                             scenario_generator=scenario_generator, provider_factory=provider_factory,
                             body_writer=fake_body_writer)
            client = TestClient(app)
            login_client(client)
            app.state.project_store.refund_wallet_credits("seller-1", 100)

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
            self.assertAlmostEqual(video["duration_sec"], 19.0, delta=0.5)  # 훅 9초 + 공용 본편 10초
            self.assertTrue(video["stream_url"] and video["srt_url"])
            self.assertEqual(client.get(f"/v1/projects/{pid}").json()["status"], "DELIVERABLE_READY")

            outputs = client.get(f"/v1/projects/{pid}/outputs").json()["outputs"]
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0]["files"]["hook_video"], "hook.mp4")
            # 결과 주소는 서명된 /v1/media/... 링크다: 그 링크로 실제로 내려받아 확인한다
            media = client.get(video["stream_url"])
            self.assertEqual(media.status_code, 200, video["stream_url"])
            final_local = root / "downloaded_master.mp4"
            final_local.write_bytes(media.content)
            self.assertEqual((probe(TOOLS, final_local).width, probe(TOOLS, final_local).height), (1080, 1920))
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
            self.assertNotEqual(done2["video"]["stream_url"], video["stream_url"])  # 작업마다 다른 최종 파일

            # 목소리를 바꾸면 예전 훅을 쓰지 않고 새로 만든다 (클립은 같은 내용이면 다시 사지 않는다)
            third = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid, "voice_id": "Puck"})
            jid3 = third.json()["job_id"]
            done3 = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                          lambda d: d.get("job_id") == jid3 and d.get("status") in ("QC_READY", "FAILED"))
            self.assertEqual(done3["status"], "QC_READY", done3)
            self.assertEqual(len(client.get(f"/v1/projects/{pid}/outputs").json()["outputs"]), 2)
            self.assertIn("Puck", {c["voice"] for p in providers for c in p.tts_calls})

    def test_render_failure_is_reported_and_missing_body_stops_before_paying(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            provider = FakeMediaProvider(TOOLS)
            state = {"fail": True}
            real_clip = provider.generate_video_clip

            def flaky_clip(*args: Any, **kwargs: Any) -> None:
                if state["fail"]:
                    raise RuntimeError("video model quota exceeded")
                real_clip(*args, **kwargs)

            provider.generate_video_clip = flaky_clip  # type: ignore[method-assign]
            client = _client(root, provider)
            pid, sid = _project_with_selected_scenario(client, "B")

            # 본편이 서버에 없는 프로젝트: 훅에 돈을 쓰기 전에 실패한다
            client.post(f"/v1/projects/{pid}/uploads/complete", json={"clips": [
                {"shot_no": 1, "object_key": "uploads/missing.mp4", "duration_sec": 6.0, "width": 1080, "height": 1920}]})
            client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid})
            lost = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                         lambda d: d.get("status") in ("QC_READY", "FAILED"))
            self.assertEqual(lost["status"], "FAILED")
            self.assertEqual((provider.tts_calls, provider.image_calls), ([], []))

            footage = make_video(TOOLS, root / "shot1.mp4", seconds=5.0)
            client.post(f"/v1/projects/{pid}/uploads/complete",
                        json={"clips": [{"shot_no": 1, "object_key": "uploads/shot1.mp4", "local_path": str(footage)}]})
            render_fail = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid})
            self.assertEqual(render_fail.status_code, 202, render_fail.text)
            self.assertEqual(render_fail.json()["deducted_credits"], 12)
            jid = render_fail.json()["job_id"]
            failed = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                           lambda d: d.get("job_id") == jid and d.get("status") in ("QC_READY", "FAILED"))
            self.assertEqual(failed["status"], "FAILED")
            self.assertIsNone(failed["video"])
            detail = client.get(f"/v1/projects/{pid}").json()
            self.assertEqual(detail["status"], "FAILED")
            self.assertIn("quota exceeded", detail["latest_job"]["error"])
            self.assertEqual(detail["latest_job"]["deducted_credits"], 12)
            self.assertEqual(detail["latest_job"]["refunded_credits"], 12)
            self.assertEqual(client.get("/v1/billing/wallet").json()["credits"], 100)
            tts_bought = len(provider.tts_calls)
            self.assertEqual(tts_bought, 3)

            # 다시 시도하면 이미 받은 나레이션·참고 이미지는 다시 사지 않는다
            state["fail"] = False
            jid2 = client.post(f"/v1/projects/{pid}/renders", json={"scenario_id": sid}).json()["job_id"]
            ok = _wait(lambda: client.get(f"/v1/projects/{pid}/deliverables").json(),
                       lambda d: d.get("job_id") == jid2 and d.get("status") in ("QC_READY", "FAILED"))
            self.assertEqual(ok["status"], "QC_READY", ok)
            self.assertEqual(client.get("/v1/billing/wallet").json()["credits"], 88)
            # 훅 나레이션은 다시 사지 않고, 새로 산 것은 공용 본편 나레이션 2문장뿐이다
            self.assertEqual((len(provider.tts_calls), len(provider.image_calls)), (tts_bought + 2, 1))

    def test_planner_scenarios_and_dry_run_mode_never_call_paid_models(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            provider = FakeMediaProvider(TOOLS)

            def planner_like(project: Dict[str, Any], types: List[str], prov: str) -> List[Dict[str, Any]]:
                items = []
                for t in types:
                    item = worker_scenario(t, f"scn_{t}_planner")
                    item["ad_spec"] = {"timeline": [{"id": "seg1", "type": "source"}], "track_archetype": "x"}
                    items.append(item)
                return items

            client = _client(root, provider, scenario_generator=planner_like)
            pid, sid = _project_with_selected_scenario(client, "C")
            hk = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid}).json()
            body = client.get(f"/v1/projects/{pid}/hooks/{hk['hook_id']}").json()
            self.assertEqual(body["status"], "done", body)
            self.assertIsNone(body["files"]["hook_video"])
            self.assertEqual(body["files"]["scenario_json"], "scenario.json")

            dry = _client(root / "dry", provider, hook_render_mode="dry_run")
            pid2, sid2 = _project_with_selected_scenario(dry, "B")
            footage = make_video(TOOLS, root / "shot.mp4", seconds=5.0)
            dry.post(f"/v1/projects/{pid2}/uploads/complete",
                     json={"clips": [{"shot_no": 1, "object_key": "uploads/shot.mp4", "local_path": str(footage)}]})
            self.assertEqual(dry.post(f"/v1/projects/{pid2}/renders", json={"scenario_id": sid2}).status_code, 202)
            self.assertEqual(dry.get(f"/v1/projects/{pid2}/deliverables").json()["status"], "DRY_RUN_READY")
            hk2 = dry.post(f"/v1/projects/{pid2}/hooks", json={"scenario_id": sid2}).json()
            self.assertIsNone(dry.get(f"/v1/projects/{pid2}/hooks/{hk2['hook_id']}").json()["files"]["hook_video"])

            self.assertEqual((provider.tts_calls, provider.image_calls, provider.video_calls), ([], [], []))

    def test_hook_endpoint_renders_once_per_scenario_and_counts_against_the_daily_limit(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            provider = FakeMediaProvider(TOOLS)
            state = {"fail": True}
            real_clip = provider.generate_video_clip

            def flaky_clip(*args: Any, **kwargs: Any) -> None:
                if state["fail"]:
                    raise RuntimeError("video model quota exceeded")
                real_clip(*args, **kwargs)

            provider.generate_video_clip = flaky_clip  # type: ignore[method-assign]
            client = _client(root, provider, daily_render_limit=2)
            pid, sid = _project_with_selected_scenario(client, "A")

            hk1 = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid, "tts": {"enabled": True}})
            self.assertEqual(hk1.status_code, 202, hk1.text)
            failed = client.get(f"/v1/projects/{pid}/hooks/{hk1.json()['hook_id']}").json()
            self.assertEqual(failed["status"], "failed")
            self.assertIn("quota exceeded", failed["error"])
            self.assertIsNone(failed["files"]["hook_video"])
            self.assertEqual(client.get(f"/v1/projects/{pid}").json()["status"], "FAILED")

            state["fail"] = False
            hk2 = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid, "tts": {"enabled": True}})
            body = client.get(f"/v1/projects/{pid}/hooks/{hk2.json()['hook_id']}").json()
            self.assertEqual(body["status"], "done", body)
            self.assertEqual(body["files"]["hook_video"], "hook.mp4")
            self.assertEqual(body["files"]["subtitles_srt"], "hook.srt")
            self.assertTrue((Path(body["output_dir"]) / "hook.mp4").is_file())
            self.assertEqual(len(provider.tts_calls), 3)  # 실패한 첫 시도에서 받은 나레이션을 다시 사지 않았다

            # 같은 시나리오·같은 목소리로 또 부르면 이미 만든 훅을 돌려주고 아무것도 새로 만들지 않는다
            calls = (len(provider.tts_calls), len(provider.image_calls), len(provider.video_calls))
            hk3 = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid, "tts": {"enabled": True}})
            self.assertEqual(hk3.status_code, 202, hk3.text)
            self.assertEqual(hk3.json()["hook_id"], hk2.json()["hook_id"])
            self.assertEqual(hk3.json()["status"], "done")
            self.assertEqual((len(provider.tts_calls), len(provider.image_calls), len(provider.video_calls)), calls)
            self.assertEqual(client.get(f"/v1/projects/{pid}").json()["quota"]["used_today"], 2)

            # 한도(2회)를 다 썼으므로 새로 만들어야 하는 요청(나레이션 끔)은 거절된다
            over = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": sid, "tts": {"enabled": False}})
            self.assertEqual(over.status_code, 429, over.text)
            self.assertEqual(over.json()["detail"]["error"]["code"], "DAILY_QUOTA_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
