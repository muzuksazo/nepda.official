"""Tests for hookpipe 3-bus BGM + transition SFX mixing and R2 audio pack resolution."""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from hookpipe.audio_mix import AudioPack, mix_bgm_and_sfx, resolve_audio_pack  # noqa: E402
from hookpipe.media import find_tools, measure_lufs, probe, run_ffmpeg  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


def _make_tone_audio(out_path: Path, freq: int, dur: float) -> None:
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
            f"{start_sec:.2f}",
            "-t",
            f"{dur_sec:.2f}",
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


class TestHookpipeAudioMix(unittest.TestCase):
    def test_mix_bgm_and_sfx_adds_bgm_with_ducking_and_preserves_duration(self) -> None:
        tools = find_tools()
        with temporary_directory() as td:
            root = Path(td)
            video_mp4 = root / "final.mp4"
            # Build 8s video where VO bursts only at [0.5..2.0] and [5.0..6.5], leaving [2.5..3.5] silent
            subprocess.run(
                [
                    tools.ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=0x224488:s=360x640:d=8:r=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=520:sample_rate=48000:duration=1.5",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=620:sample_rate=48000:duration=1.5",
                    "-filter_complex",
                    "[1:a]atrim=0:8[sil];"
                    "[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-8dB,adelay=500:all=1,apad=whole_dur=8,atrim=0:8[vo1];"
                    "[3:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-8dB,adelay=5000:all=1,apad=whole_dur=8,atrim=0:8[vo2];"
                    "[sil][vo1][vo2]amix=inputs=3:duration=first:normalize=0[aout]",
                    "-map",
                    "0:v",
                    "-map",
                    "[aout]",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-t",
                    "8",
                    str(video_mp4),
                ],
                check=True,
            )

            before_gap_db = _mean_volume_db(tools.ffmpeg, video_mp4, 2.4, 1.0)
            self.assertLess(before_gap_db, -60.0)

            hook_bgm = root / "bgm_hook_a.mp3"
            body_bgm = root / "bgm_body.mp3"
            sfx = root / "sfx_transition.mp3"
            _make_tone_audio(hook_bgm, 220, 4.0)
            _make_tone_audio(body_bgm, 330, 4.0)
            _make_tone_audio(sfx, 120, 0.35)

            lufs = mix_bgm_and_sfx(
                video_mp4,
                hook_sec=4.0,
                tools=tools,
                pack=AudioPack(hook_bgm=hook_bgm, body_bgm=body_bgm, transition_sfx=sfx),
                tmp_dir=root / "_mix",
            )
            self.assertIsNotNone(lufs)
            assert lufs is not None
            self.assertGreaterEqual(lufs, -17.0)
            self.assertLessEqual(lufs, -11.0)

            info = probe(tools, video_mp4)
            self.assertTrue(info.has_audio)
            self.assertAlmostEqual(info.duration, 8.0, delta=0.25)

            after_gap_db = _mean_volume_db(tools.ffmpeg, video_mp4, 2.4, 1.0)
            self.assertGreater(after_gap_db, -45.0)
            measured = measure_lufs(tools, video_mp4)
            self.assertIsNotNone(measured)

    def test_resolve_audio_pack_storage_cache_and_toggle(self) -> None:
        class FakeAudioStorage:
            def __init__(self, payload: bytes) -> None:
                self.payload = payload
                self.downloads: list[str] = []

            def download_file(self, object_key: str, local_path: str | Path) -> str:
                if object_key.endswith("bgm_hook_c.mp3"):
                    raise FileNotFoundError(object_key)
                self.downloads.append(object_key)
                dest = Path(local_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(self.payload)
                return str(dest)

        with temporary_directory() as td:
            root = Path(td)
            storage = FakeAudioStorage(b"ID3dummy-mp3-bytes")
            settings = Settings(
                _env_file=None,
                hook_bgm_enabled=True,
                hook_audio_location="storage:assets/audio",
                work_root=str(root / "jobs"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            cache_dir = root / "audio_cache"

            # Track B resolves bgm_hook_b.mp3 + body + sfx
            pack_b = resolve_audio_pack(settings, storage, hook_type="B", cache_dir=cache_dir)
            self.assertIsNotNone(pack_b.hook_bgm)
            self.assertEqual(pack_b.hook_bgm.name, "bgm_hook_b.mp3")
            self.assertIsNotNone(pack_b.body_bgm)
            self.assertIsNotNone(pack_b.transition_sfx)

            # Track C missing -> falls back cleanly to bgm_hook_a.mp3, reuses cached body/sfx
            dl_count_before = len(storage.downloads)
            pack_c = resolve_audio_pack(settings, storage, hook_type="C", cache_dir=cache_dir)
            self.assertIsNotNone(pack_c.hook_bgm)
            self.assertEqual(pack_c.hook_bgm.name, "bgm_hook_a.mp3")
            self.assertEqual(len(storage.downloads), dl_count_before + 1)

            # Disabled flag -> returns empty AudioPack
            disabled = Settings(
                _env_file=None,
                hook_bgm_enabled=False,
                work_root=str(root / "jobs"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            self.assertTrue(resolve_audio_pack(disabled, storage, hook_type="A", cache_dir=cache_dir).is_empty())
