"""Tests for Track A $0 storyboard hydration, Omni prompt hygiene, direct-cut render, twist-aligned audio mix, and body opening callback."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.projects_router import _default_storyboard_generator  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from app.store import JobStore  # noqa: E402
from hookpipe.audio_mix import AudioPack, mix_bgm_and_sfx  # noqa: E402
from hookpipe.body_edit import body_cache_key, make_body  # noqa: E402
from hookpipe.captions import parse_srt  # noqa: E402
from hookpipe.media import probe, run_ffmpeg  # noqa: E402
from hookpipe.prompts import COMMON_RULES, STYLE_BY_TYPE, beat_prompt  # noqa: E402
from hookpipe.render import extract_reference_frames, is_usable_reference_frame, render_hook  # noqa: E402
from hookpipe.service import HookPipeline, _opening_callback_for_scenario  # noqa: E402
from tests.support.hookpipe import FakeMediaProvider, fake_body_writer, make_video, tools_or_none  # noqa: E402
from tests.support.production import _make_sample_mp4_bytes  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402

TOOLS = tools_or_none()
PRODUCT = {
    "name": "초강력 방수 테이프",
    "category": "living",
    "verified_facts": ["실내외 초강력 접착력", "물 새는 파이프 즉시 밀봉"],
}


def _make_tone_mp3(out_path: Path, freq: int, dur: float, gain_db: float = 0.0) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate=48000:duration={dur}",
            "-af",
            f"volume={gain_db:.1f}dB",
            "-ac",
            "2",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(out_path),
        ],
        check=True,
    )


def _mean_volume_db(ffmpeg: str, media_path: Path, start_sec: float, dur_sec: float) -> float:
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-ss",
            f"{start_sec:.3f}",
            "-t",
            f"{dur_sec:.3f}",
            "-i",
            str(media_path),
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    m = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", proc.stderr or "")
    if not m:
        raise AssertionError(f"Could not parse mean_volume from ffmpeg stderr:\n{proc.stderr}")
    return float(m.group(1))


class _FakeRemoteTemplateStorage:
    """Simulates a non-local R2 template storage backend for cold Cloud Run hydration tests."""

    def __init__(self, objects: Dict[str, bytes]) -> None:
        self._objects = dict(objects)
        self.downloads: List[str] = []

    def download_file(self, object_key: str, local_path: str | Path) -> str:
        if object_key not in self._objects:
            raise FileNotFoundError(object_key)
        self.downloads.append(object_key)
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._objects[object_key])
        return str(dest)


class TestTrackAStoryboardAndAudioTwist(unittest.TestCase):
    @unittest.skipUnless(TOOLS is not None, "ffmpeg required")
    def test_track_a_storyboard_hydrates_from_r2_reads_template_id_and_includes_object_key(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            # Cold empty template dir (no local manifest or mp4)
            cold_tpl_dir = root / "cold_tpl_a"
            mp4_bytes = _make_sample_mp4_bytes(duration=4.0, w=540, h=960)
            manifest_bytes = json.dumps(
                [
                    {
                        "id": "a_r2_domino",
                        "filename": "a_r2_domino.mp4",
                        "title": "도미노 50층 실험",
                        "duration_sec": 4.0,
                        "enabled": True,
                        "default_hook_captions": ["기본 자막 1", "기본 자막 2", "기본 자막 3"],
                    }
                ],
                ensure_ascii=False,
            ).encode("utf-8")
            remote_tpl_storage = _FakeRemoteTemplateStorage(
                {
                    "templates/a/manifest.json": manifest_bytes,
                    "templates/a/a_r2_domino/beat_01.mp4": mp4_bytes,
                }
            )
            settings = Settings(
                _env_file=None,
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
                track_a_template_dir=str(cold_tpl_dir),
                hook_a_templates="storage:templates/a",
            )
            storage = LocalStorageBackend(root / "objects")
            gen = _default_storyboard_generator(
                settings, storage, template_storage=remote_tpl_storage
            )
            project = {"project_id": "prj_r2_sb", "user_id": "u1", "product": PRODUCT}
            # Uses `ad_spec.template_id` (not `track_a_template_id`) + `caption_cues` + Beat 2 "정지"
            scenario = {
                "scenario_id": "scn_r2_a1",
                "type": "A",
                "ad_spec": {"template_id": "a_r2_domino"},
                "beats": [
                    {
                        "order": 1,
                        "role": "어긋난 시작",
                        "duration_sec": 4.0,
                        "visual": "도미노가 쓰러진다",
                        "caption": "1cm 도미노",
                        "caption_cues": ["1cm 도미노를 2배씩", "스무 개만 세우면", "50층 높이로 강타"],
                    },
                    {
                        "order": 2,
                        "role": "패턴 인터럽트",
                        "duration_sec": 0.3,
                        "visual": "정지",
                        "narration": "",
                        "caption": "",
                    },
                ],
            }
            with patch(
                "app.projects_router.GenAIMediaProvider",
                side_effect=AssertionError("Track A storyboard must not call GenAIMediaProvider"),
            ):
                frames = gen(project, scenario, "default")

            self.assertEqual(len(frames), 4)
            self.assertIn("templates/a/manifest.json", remote_tpl_storage.downloads)
            self.assertIn("templates/a/a_r2_domino/beat_01.mp4", remote_tpl_storage.downloads)
            self.assertEqual(frames[0]["caption"], "1cm 도미노를 2배씩")
            self.assertEqual(frames[1]["caption"], "스무 개만 세우면")
            self.assertEqual(frames[2]["caption"], "50층 높이로 강타")
            for idx, frame in enumerate(frames, start=1):
                self.assertEqual(frame["beat_order"], idx)
                self.assertEqual(
                    frame["object_key"],
                    f"projects/prj_r2_sb/storyboards/scn_r2_a1/frame_{idx:02d}.png",
                )
                self.assertNotIn("정지", frame["caption"])
                self.assertTrue(frame["image_url"].startswith("/v1/media/"))

    def test_server_passes_hook_a_storage_as_template_storage_to_projects_router(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            captured: Dict[str, Any] = {}
            from app import projects_router as pr_mod

            orig_build = pr_mod.build_projects_router

            def _spy_build(*args: Any, **kwargs: Any) -> Any:
                captured["template_storage"] = kwargs.get("template_storage")
                return orig_build(*args, **kwargs)

            with patch("app.server.build_projects_router", side_effect=_spy_build):
                app = create_app(settings=settings)
            self.assertIsNotNone(captured.get("template_storage"))
            self.assertIs(captured["template_storage"], app.state.hook_a_storage)

    def test_storyboard_fallback_skips_pause_interrupt_and_jeongji_beats_across_all_tracks(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            storage = LocalStorageBackend(root / "objects")
            seen_prompts: List[str] = []

            class _SpyProvider:
                def __init__(self, _cfg: Any) -> None:
                    pass

                def generate_reference_image(self, prompt: str, out_path: Path, **_kw: Any) -> Any:
                    seen_prompts.append(prompt)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
                    return SimpleNamespace(skipped=False, elapsed_sec=0.01)

            gen = _default_storyboard_generator(settings, storage)
            project = {"project_id": "prj_skip_pause", "user_id": "u1", "product": PRODUCT}
            scenario = {
                "scenario_id": "scn_b_pause",
                "type": "B",
                "beats": [
                    {"order": 1, "role": "어긋난 시작", "duration_sec": 3.0, "visual": "바닷속 문어 클로즈업", "caption": "문어"},
                    {"order": 2, "role": "패턴 인터럽트", "duration_sec": 0.3, "visual": "정지", "caption": ""},
                    {"order": 3, "role": "silence_gap", "duration_sec": 0.25, "visual": "반전 전환 구간", "caption": ""},
                    {"order": 4, "role": "전환", "duration_sec": 0.5, "visual": "짧은 컷", "caption": ""},
                    {"order": 5, "role": "설명", "duration_sec": 3.0, "visual": "", "caption": ""},
                    {"order": 6, "role": "실물 착지", "duration_sec": 4.0, "visual": "파이프에 방수 테이프를 감는다", "caption": "즉시 밀봉"},
                ],
            }
            with patch("app.projects_router.GenAIMediaProvider", _SpyProvider):
                frames = gen(project, scenario, "default")

            self.assertEqual([f["beat_order"] for f in frames], [1, 6])
            self.assertEqual(len(seen_prompts), 2)
            self.assertTrue(all("정지" not in p for p in seen_prompts))
            self.assertIn("바닷속 문어 클로즈업", seen_prompts[0])
            self.assertIn("파이프에 방수 테이프를 감는다", seen_prompts[1])

    def test_omni_prompt_hygiene_track_a_product_and_no_bottom_third_box(self) -> None:
        self.assertNotIn("Keep the bottom third calm", COMMON_RULES)
        self.assertIn(
            "Frame the main subject in the upper two-thirds with natural, continuous background extending cleanly to the bottom edge (no bars, borders, boxes, or overlays)",
            COMMON_RULES,
        )

        scenario_a = {
            "type": "A",
            "hook_title": "1cm 도미노를 2배씩 스무 개만 세우면",
            "ad_spec": {"visual_style": "desert clay diorama"},
            "beats": [
                {"order": 1, "role": "어긋난 시작", "duration_sec": 9.9, "visual": "사막 위 도미노"},
                {"order": 2, "role": "패턴 인터럽트", "duration_sec": 0.3, "visual": "정지"},
                {"order": 3, "role": "담백한 실물 착지", "duration_sec": 5.0, "visual": "싱크대 아래 파이프에 방수 테이프를 감는다"},
            ],
        }
        prod_prompt = beat_prompt(
            scenario_a,
            scenario_a["beats"][2],
            3,
            3,
            product=PRODUCT,
            shows_product=True,
            has_product_reference=True,
            has_style_reference=True,
        )
        self.assertIn(STYLE_BY_TYPE["C"], prod_prompt)
        self.assertNotIn(STYLE_BY_TYPE["A"], prod_prompt)
        self.assertNotIn("desert clay diorama", prod_prompt)
        self.assertNotIn("STORY (told over", prod_prompt)
        self.assertNotIn("도미노", prod_prompt)
        self.assertNotIn("Keep the same look", prod_prompt)
        self.assertNotIn("Keep the same main character", prod_prompt)
        self.assertIn("싱크대 아래 파이프에 방수 테이프를 감는다", prod_prompt)

        # Non-product Track A shot keeps Track A style and story context
        opener_prompt = beat_prompt(
            scenario_a,
            scenario_a["beats"][0],
            1,
            3,
            product=PRODUCT,
            shows_product=False,
        )
        self.assertIn(STYLE_BY_TYPE["A"], opener_prompt)
        self.assertIn("STORY (told over 3 shots): 1cm 도미노를 2배씩 스무 개만 세우면", opener_prompt)

    @unittest.skipUnless(TOOLS is not None, "ffmpeg required")
    def test_render_hook_track_a_direct_cut_multi_cue_srt_and_twist_sec(self) -> None:
        assert TOOLS is not None
        with temporary_directory() as td:
            root = Path(td)
            tpl_clip = make_video(TOOLS, root / "assets" / "a_domino" / "beat_01.mp4", seconds=4.0, audio=True)
            provider = FakeMediaProvider(TOOLS, seconds_per_char=0.05)
            settings = SimpleNamespace(
                hook_max_sec=20.0,
                hook_clip_resolution="720p",
                hook_burn_captions=True,
                hook_max_clip_sec_per_hook=45,
                video_model="gemini-omni-flash-preview",
                tts_model="fake-tts",
                ffmpeg_bin=None,
                ffprobe_bin=None,
            )

            # 1) Direct-Cut 2-beat Track A (zero Omni clips, multi-cue caption_cues)
            scenario_direct = {
                "scenario_id": "sc_a_direct",
                "type": "A",
                "hook_title": "1cm 도미노를 2배씩",
                "beats": [
                    {
                        "order": 1,
                        "role": "어긋난 시작",
                        "duration_sec": 3.9,
                        "visual": "도미노 연쇄 반응",
                        "narration": "일 센티미터 도미노를 두 배씩 키워 봤습니다.",
                        "caption": "1cm 도미노를 2배씩",
                        "caption_cues": [
                            "1cm 도미노를 2배씩",
                            "스무 개만 세우면",
                            "아파트 50층 높이",
                        ],
                        "prebuilt_clip": "a_domino/beat_01.mp4",
                    },
                    {
                        "order": 2,
                        "role": "패턴 인터럽트",
                        "duration_sec": 0.3,
                        "visual": "정지",
                        "narration": "",
                        "caption": "",
                    },
                ],
                "ad_spec": {
                    "template_id": "a_domino",
                    "twist_callback_line": "도미노처럼 번지기 전에, 누수는 한 번에 잡아야 합니다.",
                },
            }
            out_direct = root / "hook_direct"
            res = render_hook(
                scenario_direct,
                PRODUCT,
                out_direct,
                provider=provider,
                settings=settings,
                tools=TOOLS,
                resolve_asset=lambda ref: tpl_clip if ref == "a_domino/beat_01.mp4" else None,
            )
            self.assertEqual(len(provider.video_calls), 0)
            self.assertEqual(len(provider.image_calls), 0)
            self.assertAlmostEqual(res.duration_sec, 4.2, delta=0.25)

            meta = json.loads((out_direct / "render_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["requested_clip_sec"], 0)
            self.assertAlmostEqual(meta["twist_sec"], 4.2, delta=0.25)

            srt_cues = parse_srt((out_direct / "hook.srt").read_text(encoding="utf-8"))
            self.assertEqual(len(srt_cues), 3)
            self.assertEqual([c[2] for c in srt_cues], ["1cm 도미노를 2배씩", "스무 개만 세우면", "아파트 50층 높이"])
            self.assertAlmostEqual(srt_cues[0][0], 0.0, places=2)
            self.assertAlmostEqual(srt_cues[0][1], 1.3, places=2)
            self.assertAlmostEqual(srt_cues[1][1], 2.6, places=2)
            self.assertAlmostEqual(srt_cues[2][1], 3.9, places=2)

            # 2) 3-beat Track A with AI landing -> twist_sec marks end of Beat 2 (4.2s), NOT total hook (7.2s)
            scenario_3beat = {
                **scenario_direct,
                "scenario_id": "sc_a_3beat",
                "beats": [
                    *scenario_direct["beats"],
                    {
                        "order": 3,
                        "role": "담백한 실물 착지",
                        "duration_sec": 3.0,
                        "visual": "싱크대 파이프에 테이프 감기",
                        "narration": "새는 파이프를 즉시 밀봉합니다.",
                        "caption": "파이프 즉시 밀봉",
                    },
                ],
            }
            out_3beat = root / "hook_3beat"
            res3 = render_hook(
                scenario_3beat,
                PRODUCT,
                out_3beat,
                provider=provider,
                settings=settings,
                tools=TOOLS,
                resolve_asset=lambda ref: tpl_clip if ref == "a_domino/beat_01.mp4" else None,
            )
            meta3 = json.loads((out_3beat / "render_meta.json").read_text(encoding="utf-8"))
            self.assertGreater(res3.duration_sec, 6.8)
            self.assertAlmostEqual(meta3["twist_sec"], 4.2, delta=0.2)

    @unittest.skipUnless(TOOLS is not None, "ffmpeg required")
    def test_reference_frame_sanity_rejects_testsrc2_smptebars_and_flat_frames(self) -> None:
        assert TOOLS is not None
        with temporary_directory() as td:
            root = Path(td)
            for name, src in [
                ("testsrc2", "testsrc2=size=360x640:rate=24:duration=2"),
                ("smptebars", "smptebars=size=360x640:rate=24:duration=2"),
                ("flat_teal", "color=c=teal:s=360x640:d=2:r=24"),
            ]:
                vid = root / f"{name}.mp4"
                run_ffmpeg(
                    TOOLS,
                    ["-f", "lavfi", "-i", src, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(vid)],
                )
                refs = extract_reference_frames([vid], root / f"refs_{name}", TOOLS)
                self.assertEqual(refs, [], f"Synthetic/flat video {name} must not produce Omni reference frames")

            # Directly passed bad frame is also detected and excluded by render_hook
            bad_jpg = root / "bad_testsrc2.jpg"
            run_ffmpeg(TOOLS, ["-f", "lavfi", "-i", "testsrc2=size=360x640:rate=24:duration=1", "-frames:v", "1", str(bad_jpg)])
            ok_bad, reason_bad = is_usable_reference_frame(bad_jpg)
            self.assertFalse(ok_bad)
            self.assertEqual(reason_bad, "synthetic_test_pattern")

            # Real video frame from bundled template passes sanity check untouched
            bundled = sorted((BACKEND / "data" / "templates" / "track_a").glob("*.mp4"))
            if bundled:
                good_refs = extract_reference_frames([bundled[0]], root / "refs_real", TOOLS)
                self.assertEqual(len(good_refs), 2)

    @unittest.skipUnless(TOOLS is not None, "ffmpeg required")
    def test_mix_bgm_and_sfx_aligns_dead_stop_and_sfx_to_twist_sec(self) -> None:
        assert TOOLS is not None
        with temporary_directory() as td:
            root = Path(td)
            hook_bgm = root / "bgm_hook_a.mp3"
            body_bgm = root / "bgm_body.mp3"
            sfx = root / "sfx_transition.mp3"
            _make_tone_mp3(hook_bgm, 220, 6.0)
            _make_tone_mp3(body_bgm, 330, 8.0)
            _make_tone_mp3(sfx, 150, 0.30, gain_db=0.0)

            # Case 1: BGM dead-stop aligns to twist_sec=4.0 (gap [3.70..4.00]), NOT hook_sec=8.0
            vid_bgm = root / "silent_bgm.mp4"
            run_ffmpeg(
                TOOLS,
                [
                    "-f", "lavfi", "-i", "color=c=0x223344:s=360x640:d=12:r=30",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-t", "12", str(vid_bgm),
                ],
            )
            mix_bgm_and_sfx(
                vid_bgm,
                hook_sec=8.0,
                twist_sec=4.0,
                tools=TOOLS,
                pack=AudioPack(hook_bgm=hook_bgm, body_bgm=body_bgm, transition_sfx=None),
                tmp_dir=root / "_mix_bgm",
            )
            act1_db = _mean_volume_db(TOOLS.ffmpeg, vid_bgm, 1.5, 1.0)
            twist_gap_db = _mean_volume_db(TOOLS.ffmpeg, vid_bgm, 3.74, 0.22)
            hook_end_db = _mean_volume_db(TOOLS.ffmpeg, vid_bgm, 7.74, 0.22)
            self.assertLess(twist_gap_db, act1_db - 15.0, (act1_db, twist_gap_db, hook_end_db))
            self.assertGreater(hook_end_db, twist_gap_db + 15.0, (act1_db, twist_gap_db, hook_end_db))

            # Case 2: Transition SFX fires at twist_sec - 0.30 (3.70s), NOT hook_sec - 0.30 (7.70s)
            vid_sfx = root / "silent_sfx.mp4"
            run_ffmpeg(
                TOOLS,
                [
                    "-f", "lavfi", "-i", "color=c=0x223344:s=360x640:d=12:r=30",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-t", "12", str(vid_sfx),
                ],
            )
            mix_bgm_and_sfx(
                vid_sfx,
                hook_sec=8.0,
                twist_sec=4.0,
                tools=TOOLS,
                pack=AudioPack(hook_bgm=None, body_bgm=None, transition_sfx=sfx),
                tmp_dir=root / "_mix_sfx",
            )
            sfx_at_twist_db = _mean_volume_db(TOOLS.ffmpeg, vid_sfx, 3.70, 0.30)
            sfx_at_hook_db = _mean_volume_db(TOOLS.ffmpeg, vid_sfx, 7.70, 0.30)
            self.assertGreater(sfx_at_twist_db, -30.0)
            self.assertLess(sfx_at_hook_db, -55.0)

    @unittest.skipUnless(TOOLS is not None, "ffmpeg required")
    def test_opening_callback_body_cache_and_service_process_render_wiring(self) -> None:
        assert TOOLS is not None
        with temporary_directory() as td:
            root = Path(td)
            clip = make_video(TOOLS, root / "upload_01.mp4", seconds=6.0, width=360, height=640)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                tts_provider="gemini",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
                hook_assets_dir=str(root / "assets"),
                body_target_sec=6.0,
                hook_bgm_enabled=True,
                hook_audio_location=str(root / "audio_stems"),
            )

            # Cache key must include opening_callback and preserve None == "" parity
            k_none = body_cache_key([clip], PRODUCT, settings, "Kore")
            k_empty = body_cache_key([clip], PRODUCT, settings, "Kore", opening_callback="")
            k_cb1 = body_cache_key([clip], PRODUCT, settings, "Kore", opening_callback="콜백 A")
            k_cb2 = body_cache_key([clip], PRODUCT, settings, "Kore", opening_callback="콜백 B")
            self.assertEqual(k_none, k_empty)
            self.assertNotEqual(k_none, k_cb1)
            self.assertNotEqual(k_cb1, k_cb2)

            # Direct-cut scenario returns twist_callback_line; AI-landing scenario returns None
            direct_scn = {
                "scenario_id": "sc_a_cb",
                "type": "A",
                "hook_title": "1cm 도미노",
                "beats": [
                    {
                        "order": 1,
                        "role": "어긋난 시작",
                        "duration_sec": 3.7,
                        "visual": "도미노",
                        "narration": "도미노가 쓰러집니다.",
                        "caption": "1cm 도미노",
                        "caption_cues": ["1cm 도미노", "50층 높이"],
                        "prebuilt_clip": "a_domino/beat_01.mp4",
                    },
                    {
                        "order": 2,
                        "role": "패턴 인터럽트",
                        "duration_sec": 0.3,
                        "visual": "정지",
                        "narration": "",
                        "caption": "",
                    },
                ],
                "ad_spec": {
                    "template_id": "a_domino",
                    "twist_callback_line": "도미노처럼 번지기 전에, 누수는 한 번에 잡아야 합니다.",
                },
            }
            self.assertEqual(
                _opening_callback_for_scenario(direct_scn),
                "도미노처럼 번지기 전에, 누수는 한 번에 잡아야 합니다.",
            )
            ai_landing_scn = {
                **direct_scn,
                "beats": [
                    *direct_scn["beats"],
                    {"order": 3, "role": "담백한 실물 착지", "duration_sec": 4.0, "visual": "파이프", "narration": "밀봉합니다."},
                ],
            }
            self.assertIsNone(_opening_callback_for_scenario(ai_landing_scn))
            self.assertIsNone(_opening_callback_for_scenario({**direct_scn, "type": "B"}))

            # End-to-end HookPipeline.process_render: verifies opening_callback + twist_sec wiring
            make_video(TOOLS, root / "assets" / "a_domino" / "beat_01.mp4", seconds=4.0, audio=True)
            audio_dir = root / "audio_stems"
            audio_dir.mkdir(parents=True, exist_ok=True)
            _make_tone_mp3(audio_dir / "bgm_hook_a.mp3", 220, 4.0)
            _make_tone_mp3(audio_dir / "bgm_body.mp3", 330, 6.0)
            _make_tone_mp3(audio_dir / "sfx_transition.mp3", 150, 0.30)

            proj_store = ProjectStore(settings.db_path)
            job_store = JobStore(settings.db_path)
            storage = LocalStorageBackend(root / "objects")
            proj = proj_store.create_project(
                "prj_a_e2e",
                "usr_1",
                product=PRODUCT,
                selected_types=["A"],
                flow_mode="guide_first",
            )
            proj_store.update_project(
                proj["project_id"],
                uploads={"clips": [{"shot_no": 1, "local_path": str(clip)}]},
            )
            job_store.create_job("job_a_e2e", proj["project_id"], {}, status="QUEUED", stage="QUEUED")

            body_prompts: List[str] = []

            def _spy_body_writer(prompt: str, frames: Any) -> Dict[str, Any]:
                body_prompts.append(prompt)
                return fake_body_writer(prompt, frames)

            mix_calls: List[Dict[str, Any]] = []
            orig_mix = mix_bgm_and_sfx

            def _spy_mix(video_mp4: Path, **kw: Any) -> Optional[float]:
                mix_calls.append(dict(kw))
                return orig_mix(video_mp4, **kw)

            provider = FakeMediaProvider(TOOLS, seconds_per_char=0.06)
            hp = HookPipeline(
                settings,
                proj_store,
                job_store,
                storage,
                provider_factory=lambda _cfg: provider,
                tools=TOOLS,
                body_writer=_spy_body_writer,
            )
            with patch("hookpipe.service.mix_bgm_and_sfx", side_effect=_spy_mix):
                hp.process_render(proj["project_id"], "job_a_e2e", "usr_1", direct_scn, voice="Kore")

            job = job_store.get_job("job_a_e2e")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "QC_READY", job.get("error"))
            self.assertEqual(len(provider.video_calls), 0)
            self.assertEqual(len(body_prompts), 1)
            self.assertIn("도미노처럼 번지기 전에, 누수는 한 번에 잡아야 합니다.", body_prompts[0])
            self.assertEqual(len(mix_calls), 1)
            self.assertAlmostEqual(mix_calls[0]["twist_sec"], 4.0, delta=0.25)
            # Callback-specific body must NOT overwrite generic project.body for Track B/C
            refreshed = proj_store.get_project(proj["project_id"])
            self.assertIsNone((refreshed or {}).get("body"))


if __name__ == "__main__":
    unittest.main()
