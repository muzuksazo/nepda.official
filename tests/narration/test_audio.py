"""Offline regression coverage organized by PRD area."""
from tests.support.media_tools import (
    AudioPrepCase,
    _write_test_wav,
    ad_audio_prep,
    json,
    os,
    tempfile,
)
from tests.support.tempdirs import temporary_directory


class TestAudioPrep(AudioPrepCase):
    def test_probe_islands_and_manifest_subslice(self) -> None:
        with temporary_directory() as td:
            wav_path = os.path.join(td, "sample.wav")
            _write_test_wav(wav_path)

            probed = ad_audio_prep.probe_islands(wav_path, silence_db=-39.0, min_silence=0.15)
            self.assertEqual(probed["island_count"], 2)
            self.assertAlmostEqual(probed["islands"][0]["start"], 0.16, delta=0.06)
            self.assertAlmostEqual(probed["islands"][1]["start"], 1.26, delta=0.06)
            self.assertGreaterEqual(probed["islands"][0]["gap_after"], 0.30)

            manifest_path = os.path.join(td, "vo_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "beats": [
                            {
                                "id": "VO_1",
                                "file": "sample.wav",
                                "start_sec": probed["islands"][0]["start"],
                                "end_sec": probed["islands"][0]["end"],
                                "trim_edges": False,
                                "gap_after": 0.28,
                                "text": "첫 문장",
                            },
                            {
                                "id": "VO_2",
                                "file": "sample.wav",
                                "start_sec": probed["islands"][1]["start"],
                                "end_sec": probed["islands"][1]["end"],
                                "trim_edges": False,
                                "gap_after": 0.0,
                                "text": "둘째 문장",
                            },
                        ]
                    },
                    f,
                    ensure_ascii=False,
                )

            out_wav = os.path.join(td, "vo_master.wav")
            out_json = os.path.join(td, "vo_segments.json")
            built = ad_audio_prep.build_manifest_vo(manifest_path, out_wav, out_json)
            self.assertEqual(built["segment_count"], 2)
            self.assertAlmostEqual(built["segments"][0]["gap_after"], 0.28, places=2)
            gap_actual = built["segments"][1]["start"] - built["segments"][0]["end"]
            self.assertAlmostEqual(gap_actual, 0.28, delta=0.02)
            self.assertTrue(os.path.exists(out_wav))

            # Verify speed!=1.0 slices raw start_sec/end_sec BEFORE atempo, without slicing past the end
            fast_manifest = os.path.join(td, "vo_fast.json")
            with open(fast_manifest, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "beats": [
                            {
                                "id": "FAST_1",
                                "file": "sample.wav",
                                "start_sec": probed["islands"][1]["start"],
                                "end_sec": probed["islands"][1]["end"],
                                "speed": 1.25,
                                "trim_edges": False,
                                "gap_after": 0.0,
                                "text": "빠른 둘째 문장",
                            }
                        ]
                    },
                    f,
                    ensure_ascii=False,
                )
            fast_wav = os.path.join(td, "vo_fast.wav")
            fast_json = os.path.join(td, "vo_fast_segments.json")
            fast_built = ad_audio_prep.build_manifest_vo(fast_manifest, fast_wav, fast_json)
            raw_island_dur = probed["islands"][1]["end"] - probed["islands"][1]["start"]
            self.assertAlmostEqual(fast_built["segments"][0]["duration"], raw_island_dur / 1.25, delta=0.06)
