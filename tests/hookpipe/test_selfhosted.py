"""자체 모델(FLUX·MiniMax) 경로: 콘티 API 와 영상 단계가 가짜 모델로 이어지는지 (과금·GPU·ffmpeg 없음)."""

import base64
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest import mock

from tests.support.hookpipe import worker_scenario

from hookpipe.selfhosted import STYLE_REF_LEAD, SelfHostedMedia, clip_frames
from hookpipe.service import HookPipeline


class _Call:
    def __init__(self, fn: Any) -> None:
        self.remote = fn
        self.spawned: List[Any] = []

    def spawn(self, *args: Any) -> None:
        self.spawned.append(args)


class _Flux:
    def __init__(self) -> None:
        self.payloads: List[Dict[str, Any]] = []
        self.run_generate = _Call(self._gen)

    def _gen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.payloads.append(payload)
        n = len(self.payloads)
        return {"image_base64": base64.b64encode(f"png{n}".encode()).decode(), "latency_ms": 1}


class _MiniMax:
    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self.warm = _Call(lambda slot: None)
        self.render = SimpleNamespace(starmap=self._starmap)

    def _starmap(self, calls: List[tuple]) -> List[bytes]:
        self.calls.extend(calls)
        return [b"mp4:" + c[0] for c in calls]


def _media(flux: _Flux, minimax: _MiniMax) -> SelfHostedMedia:
    return SelfHostedMedia(SimpleNamespace(), flux=flux, minimax=minimax,
                           caption_fn=lambda spec: "caption", motion_fn=lambda spec: "motion")


class _Storage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def upload_file(self, local: Path, key: str) -> None:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, dest)

    def download_file(self, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.root / key, dest)


class SelfHostedMediaTest(unittest.TestCase):
    def test_storyboard_draws_scene_one_first_and_uses_it_as_reference(self) -> None:
        flux, minimax = _Flux(), _MiniMax()
        frames = _media(flux, minimax).storyboard(worker_scenario("B"), {"name": "타이머"})
        self.assertEqual([f["beat_order"] for f in frames], [1, 2, 3])
        self.assertEqual(flux.payloads[0]["reference_images"], [])
        self.assertEqual(flux.payloads[1]["reference_images"], [base64.b64encode(b"png1").decode()])
        self.assertTrue(flux.payloads[1]["prompt"].startswith(STYLE_REF_LEAD))
        self.assertEqual((flux.payloads[0]["width"], flux.payloads[0]["height"]), (576, 1024))
        self.assertEqual(frames[0]["png"], b"png1")
        self.assertEqual(frames[2]["motion_prompt"], "motion")
        # 장면마다 촬영 크기가 다르게 배정된다 (참고 컷 구도를 베끼지 않게)
        shots = [f["spec"].rsplit("SHOT SIZE: ", 1)[1] for f in frames]
        self.assertEqual(len(set(shots)), 3)
        self.assertIn("hero close-up of the product", shots[2])

    def test_clips_use_turbo_steps_and_17k_plus_5_frames(self) -> None:
        minimax = _MiniMax()
        out = _media(_Flux(), minimax).clips([(b"a", "m", 3.0)])
        self.assertEqual(out, [b"mp4:a"])
        _, motion, w, h, length, steps, _ = minimax.calls[0]
        self.assertEqual((motion, w, h, steps), ("m", 576, 1024, 8))
        self.assertEqual((length - 5) % 17, 0)
        self.assertGreaterEqual(length, 96)
        self.assertEqual(clip_frames(0.1), 5)


class RenderStageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.storage = _Storage(self.tmp / "bucket")
        self.settings = SimpleNamespace(hook_media_engine="selfhosted", hook_assets_dir=str(self.tmp / "assets"),
                                        hook_a_templates="storage:templates/a")
        self.flux, self.minimax = _Flux(), _MiniMax()
        self.pipe = HookPipeline(self.settings, None, None, self.storage,
                                 selfhosted_media=_media(self.flux, self.minimax))

    def test_uses_storyboard_stills_and_sets_prebuilt_clips(self) -> None:
        sc = worker_scenario("B")
        frames = []
        for order in (1, 2, 3):
            key = f"projects/p1/storyboards/s1/frame_{order:02d}.png"
            (self.tmp / "bucket" / key).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / "bucket" / key).write_bytes(f"still{order}".encode())
            frames.append({"beat_order": order, "object_key": key, "motion_prompt": f"move{order}"})
        sc["storyboard_frames"] = frames
        out = self.pipe._selfhosted_clips({"project_id": "p1"}, sc, "job1")
        self.assertEqual(self.flux.payloads, [])  # 콘티가 있으면 다시 그리지 않는다
        self.assertEqual([c[1] for c in self.minimax.calls], ["move1", "move2", "move3"])
        for beat in out["beats"]:
            ref = beat["prebuilt_clip"]
            self.assertFalse(Path(ref).is_absolute())
            found = self.pipe.resolve_asset(ref, self.tmp / "work")
            self.assertEqual(found.read_bytes(), f"mp4:still{beat['order']}".encode())
        self.assertNotIn("prebuilt_clip", sc["beats"][0])  # 원본은 그대로

    def test_draws_stills_when_storyboard_is_missing(self) -> None:
        out = self.pipe._selfhosted_clips({"project_id": "p1", "product": {}}, worker_scenario("B"), "job2")
        self.assertEqual(len(self.flux.payloads), 3)
        self.assertEqual(len(self.minimax.calls), 3)
        self.assertTrue(all(b.get("prebuilt_clip") for b in out["beats"]))

    def test_type_a_and_gemini_engine_keep_old_path(self) -> None:
        self.assertFalse(self.pipe._selfhosted(worker_scenario("A")))
        self.assertTrue(self.pipe._selfhosted(worker_scenario("B")))
        self.settings.hook_media_engine = "gemini"
        self.assertFalse(self.pipe._selfhosted(worker_scenario("B")))


class StoryboardFirstFrameTest(unittest.TestCase):
    """구글 모델 엔진: 콘티 스틸컷이 장면 클립의 구도 참고로 붙는다."""

    def _pipe(self, **settings: Any) -> HookPipeline:
        return HookPipeline(SimpleNamespace(hook_media_engine="gemini", **settings), None, None, None)

    def _scenario(self, kind: str = "C") -> Dict[str, Any]:
        sc = worker_scenario(kind)
        sc["storyboard_frames"] = [
            {"beat_order": order, "object_key": f"projects/p1/storyboards/s1/frame_{order:02d}.png"} for order in (1, 2)
        ]
        return sc

    def test_stills_become_layout_references(self) -> None:
        sc = self._scenario()
        out = self._pipe()._with_storyboard_first_frames(sc)
        self.assertEqual(out["beats"][0]["first_frame_ref"], "projects/p1/storyboards/s1/frame_01.png")
        self.assertEqual(out["beats"][1]["first_frame_ref"], "projects/p1/storyboards/s1/frame_02.png")
        self.assertIn("photorealistic", out["beats"][0]["first_frame_prompt"])
        self.assertNotIn("first_frame_refine", out["beats"][0])  # 콘티 화풍을 그대로 쓰지 않고 실사로 바꾼다
        self.assertNotIn("first_frame_ref", out["beats"][2])  # 콘티가 없는 장면은 그대로
        self.assertNotIn("first_frame_ref", sc["beats"][0])  # 원본은 그대로

    def test_keeps_existing_layout_reference_and_prebuilt_clips(self) -> None:
        sc = self._scenario()
        sc["beats"][0].update({"first_frame_ref": "c/blockouts/phone_distract.png", "first_frame_prompt": "blockout"})
        sc["beats"][1]["prebuilt_clip"] = "sh/clip2.mp4"
        out = self._pipe()._with_storyboard_first_frames(sc)
        self.assertEqual(out["beats"][0]["first_frame_ref"], "c/blockouts/phone_distract.png")  # C 블록아웃이 우선
        self.assertEqual(out["beats"][0]["first_frame_prompt"], "blockout")
        self.assertNotIn("first_frame_ref", out["beats"][1])

    def test_skips_type_a_and_can_be_turned_off(self) -> None:
        a = self._scenario("A")
        self.assertIs(self._pipe()._with_storyboard_first_frames(a), a)
        c = self._scenario()
        self.assertIs(self._pipe(hook_storyboard_first_frame=False)._with_storyboard_first_frames(c), c)
        plain = worker_scenario("C")
        self.assertIs(self._pipe()._with_storyboard_first_frames(plain), plain)


class StoryboardApiTest(unittest.TestCase):
    def test_frames_keep_object_key_and_motion_and_warm_minimax(self) -> None:
        from app import projects_router

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        storage = _Storage(tmp / "bucket")
        flux, minimax = _Flux(), _MiniMax()
        settings = SimpleNamespace(work_root=str(tmp / "jobs"))
        fallback = mock.Mock(return_value=[{"beat_order": 1}])
        gen = projects_router._selfhosted_storyboard_generator(settings, storage, fallback, media=_media(flux, minimax))
        with mock.patch.object(projects_router, "resolve_media_url", lambda key, **kw: f"/v1/media/{key}"):
            frames = gen({"project_id": "p1", "product": {}}, {**worker_scenario("B"), "scenario_id": "s1"}, "")
        self.assertEqual([f["beat_order"] for f in frames], [1, 2, 3])
        self.assertEqual(frames[0]["object_key"], "projects/p1/storyboards/s1/frame_01.png")
        self.assertEqual(frames[0]["image_url"], "/v1/media/projects/p1/storyboards/s1/frame_01.png")
        self.assertEqual(frames[1]["motion_prompt"], "motion")
        self.assertTrue((tmp / "bucket" / frames[2]["object_key"]).is_file())
        self.assertEqual(len(minimax.warm.spawned), 1)  # 비용: 1대만 미리 켠다
        fallback.assert_not_called()
        self.assertEqual(gen({"project_id": "p1"}, {**worker_scenario("A"), "scenario_id": "s2"}, ""), [{"beat_order": 1}])



class VoicePickTest(unittest.TestCase):
    def _pipe(self, ids: str) -> HookPipeline:
        return HookPipeline(SimpleNamespace(inworld_voice_ids=ids, tts_default_voice="Kore"), None, None, None)

    def test_random_from_pool_unless_requested(self) -> None:
        pipe = self._pipe("a, b,c,d")
        picked = {pipe.pick_voice(None) for _ in range(200)} | {pipe.pick_voice("Kore") for _ in range(200)}
        self.assertEqual(picked, {"a", "b", "c", "d"})
        self.assertEqual(pipe.pick_voice("chosen"), "chosen")
        self.assertIsNone(self._pipe("").pick_voice(None))

    def test_body_cache_differs_by_voice(self) -> None:
        from hookpipe.body_edit import body_cache_key

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        clip = tmp / "c.mp4"
        clip.write_bytes(b"x")
        s = SimpleNamespace()
        self.assertNotEqual(body_cache_key([clip], {}, s, "a"), body_cache_key([clip], {}, s, "b"))
        self.assertEqual(body_cache_key([clip], {}, s), body_cache_key([clip], {}, s, None))


if __name__ == "__main__":
    unittest.main()
