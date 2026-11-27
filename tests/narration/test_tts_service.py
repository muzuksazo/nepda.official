"""FR-011 · Shared Inworld TTS provider, caching, word alignment & -14 LUFS mastering tests."""

from __future__ import annotations

import base64
import io
import math
import struct
import sys
import unittest
import wave
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.tts_service import (  # noqa: E402
    InworldTTSProvider,
    measure_lufs,
    synthesize_body_narration,
)
from tests.support.tempdirs import temporary_directory  # noqa: E402


def _make_sine_wav_bytes(*, freq_hz: float = 440.0, duration_sec: float = 0.8, amp: float = 0.25, lead_sil_sec: float = 0.2) -> bytes:
    sr = 48000
    n_sil = int(round(lead_sil_sec * sr))
    n_tone = int(round(duration_sec * sr))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for _ in range(n_sil):
            frames.extend(struct.pack("<h", 0))
        for i in range(n_tone):
            val = int(round(32767.0 * amp * math.sin(2.0 * math.pi * freq_hz * i / sr)))
            frames.extend(struct.pack("<h", max(-32767, min(32767, val))))
        for _ in range(n_sil):
            frames.extend(struct.pack("<h", 0))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


class _FakeHttpResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> Dict[str, Any]:
        return self._payload


class _FakeInworldClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def post(self, url: str, *, json: Dict[str, Any], headers: Dict[str, str]) -> _FakeHttpResponse:
        self.calls.append({"url": url, "json": json, "headers": headers})
        wav_bytes = _make_sine_wav_bytes(duration_sec=0.75, amp=0.12, lead_sil_sec=0.25)
        return _FakeHttpResponse(
            200,
            {
                "audioContent": base64.b64encode(wav_bytes).decode("ascii"),
                "timestampInfo": {
                    "wordAlignment": {
                        "words": ["안녕", "하세요", "."],
                        "wordStartTimeSeconds": [0.25, 0.45, 0.85],
                        "wordEndTimeSeconds": [0.45, 0.85, 0.90],
                    }
                },
            },
        )


class TestSharedTTSService(unittest.TestCase):
    def test_inworld_synthesis_caching_word_alignment_and_lufs_mastering(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            fake_http = _FakeInworldClient()
            settings = Settings(
                _env_file=None,
                inworld_api_key="base64-test-key",
                inworld_voice_id="voice-kr-1",
                inworld_model="inworld-tts-2",
                inworld_speaking_rate=1.1,
            )
            provider = InworldTTSProvider(settings, http_client=fake_http)  # type: ignore[arg-type]

            out_wav = root / "line1.wav"
            res1 = provider.synthesize("안녕하세요.", out_wav)
            self.assertFalse(res1.cached)
            self.assertEqual(len(fake_http.calls), 1)
            self.assertEqual(fake_http.calls[0]["headers"]["Authorization"], "Basic base64-test-key")
            self.assertEqual(fake_http.calls[0]["json"]["modelId"], "inworld-tts-2")
            self.assertEqual(fake_http.calls[0]["json"]["audioConfig"]["speakingRate"], 1.1)
            # Punctuation merged into previous word
            self.assertEqual([w.word for w in res1.words], ["안녕", "하세요."])
            # Leading silence (~0.25s) trimmed down to keep_sec (0.08s)
            self.assertLess(res1.duration_sec, 1.05)

            # Second identical call hits disk cache without HTTP call
            res2 = provider.synthesize("안녕하세요.", out_wav)
            self.assertTrue(res2.cached)
            self.assertEqual(len(fake_http.calls), 1)

            # Full body narration concatenation & -14 LUFS mastering
            nar = synthesize_body_narration(
                [
                    {"narration": "첫 문장입니다.", "caption": "첫 문장"},
                    {"narration": "둘째 문장입니다.", "caption": "둘째 문장"},
                ],
                root / "body_work",
                provider,
            )
            master_wav = Path(nar["wav_path"])
            self.assertTrue(master_wav.is_file())
            self.assertEqual(len(nar["segments"]), 2)
            lufs = measure_lufs(master_wav)
            self.assertIsNotNone(lufs)
            self.assertAlmostEqual(float(lufs), -14.0, delta=2.0)
