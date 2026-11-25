"""Unit and end-to-end tests for the google-genai production ad pipeline."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

PROD_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(PROD_ROOT) not in sys.path:
    sys.path.insert(0, str(PROD_ROOT))

from app.config import Settings  # noqa: E402
from app.genai_provider import (  # noqa: E402
    BudgetExceededError,
    GenAIMediaProvider,
    build_genai_client,
    execute_jobs_file,
)
from app.pipeline import CampaignRequest, LintFailedError, ProductionPipeline  # noqa: E402
from app.server import create_app  # noqa: E402
from app.store import JobStore  # noqa: E402


def _make_sample_png_bytes(w: int = 128, h: int = 224, color: tuple = (30, 60, 120)) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "img.png"
        Image.new("RGB", (w, h), color).save(p)
        return p.read_bytes()


def _make_sample_mp4_bytes(duration: float = 5.0, w: int = 360, h: int = 640, color: str = "navy") -> bytes:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "clip.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s={w}x{h}:r=30:d={duration}",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-shortest",
                str(p),
            ],
            check=True,
        )
        return p.read_bytes()


def _make_pcm_16bit_bytes(sample_rate: int = 24000, duration: float = 0.25) -> bytes:
    n_samples = int(sample_rate * duration)
    return b"\x10\x01" * n_samples


class _FakeInteractions:
    def __init__(self, *, png_bytes: bytes, mp4_bytes: bytes, fail_video: bool = False) -> None:
        self.png_bytes = png_bytes
        self.mp4_bytes = mp4_bytes
        self.fail_video = fail_video
        self.created: list[dict] = []
        self.poll_counts: dict[str, int] = {}

    def create(self, **kwargs):
        self.created.append(kwargs)
        rf = kwargs.get("response_format") or {}
        if rf.get("type") == "image":
            return SimpleNamespace(
                id="int_img_1",
                status="completed",
                output_image=SimpleNamespace(
                    data=base64.b64encode(self.png_bytes).decode("ascii"),
                    mime_type="image/png",
                ),
            )
        vid_id = f"int_vid_{len(self.created)}"
        self.poll_counts[vid_id] = 0
        return SimpleNamespace(id=vid_id, status="in_progress")

    def get(self, id: str):
        self.poll_counts[id] = self.poll_counts.get(id, 0) + 1
        if self.poll_counts[id] < 2:
            return SimpleNamespace(id=id, status="in_progress")
        if self.fail_video:
            return SimpleNamespace(id=id, status="failed", errors=[{"message": "policy"}])
        return SimpleNamespace(
            id=id,
            status="completed",
            output_video=SimpleNamespace(
                data=base64.b64encode(self.mp4_bytes).decode("ascii"),
                mime_type="video/mp4",
            ),
        )


class _FakeModels:
    def __init__(self, *, return_wav: bool = False) -> None:
        self.return_wav = return_wav
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        pcm = _make_pcm_16bit_bytes(24000, 0.2)
        if self.return_wav:
            import io

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(pcm)
            payload = buf.getvalue()
            mime = "audio/wav"
        else:
            payload = pcm
            mime = "audio/L16;codec=pcm;rate=24000"
        return SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=payload, mime_type=mime))]
                    )
                )
            ]
        )



class GenAIClientFactoryCase(unittest.TestCase):
    pass


class GenAIMediaProviderCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.png_bytes = _make_sample_png_bytes()
        cls.mp4_bytes = _make_sample_mp4_bytes(duration=2.0)



class ProductionPipelineAndAPICase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.png_bytes = _make_sample_png_bytes(720, 1280)
        cls.mp4_bytes = _make_sample_mp4_bytes(duration=6.0, w=1080, h=1920, color="darkslategray")

    def _write_valid_campaign_inputs(self, td: Path, *, a_genre: str = "noir_interrogation", bad_c_hook: bool = False):
        src_mp4 = td / "source_product.mp4"
        src_mp4.write_bytes(self.mp4_bytes)
        vo_wav = td / "vo_master.wav"
        with wave.open(str(vo_wav), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(_make_pcm_16bit_bytes(48000, 17.5))

        facts_md = td / "00_product_facts.md"
        facts_md.write_text(
            "# Facts\n- [F01] [VERIFIED] 1000원대 소분 블록 흡수 스펀지\n",
            encoding="utf-8",
        )

        spec_path = td / "05_ad_spec.json"
        if bad_c_hook:
            cap1 = "스펀지 하나면 물기 끝"
        else:
            cap1 = "형사님 현장에 물 흔적이 증발했습니다"

        spec = {
            "project_id": f"camp-{a_genre}",
            "title": "느와르 취조실 테스트",
            "mode": "narrative_master",
            "track_archetype": "A_bgrade_reversal",
            "a_genre_archetype": a_genre,
            "product_taboo_keywords": ["스펀지"],
            "hook_window_sec": 10.0,
            "framing_mode": "full-bleed",
            "disclosure": "ai_assisted",
            "source_video": str(src_mp4),
            "source_duration": 6.0,
            "allow_static_intro": True,
            "vo_audio": str(vo_wav),
            "usps": [{"title": "강력 흡수", "fact_ids": ["F01"]}],
            "timeline": [
                {
                    "id": "H1",
                    "type": "source",
                    "src_start": 0.0,
                    "src_end": 5.0,
                    "framing": "full-bleed",
                    "audio_owner": "mute",
                },
                {
                    "id": "H2",
                    "type": "source",
                    "src_start": 0.5,
                    "src_end": 5.5,
                    "framing": "full-bleed",
                    "audio_owner": "mute",
                },
                {"id": "STOP", "type": "silence_gap", "duration": 0.25, "audio_owner": "silence"},
                {
                    "id": "P1",
                    "type": "source",
                    "src_start": 0.5,
                    "src_end": 5.5,
                    "framing": "full-bleed",
                    "audio_owner": "mute",
                    "fact_ids": ["F01"],
                },
                {
                    "id": "P2",
                    "type": "source",
                    "src_start": 0.5,
                    "src_end": 2.5,
                    "framing": "full-bleed",
                    "audio_owner": "mute",
                    "fact_ids": ["F01"],
                },
            ],
            "captions": [
                {"start": 0.0, "end": 4.9, "text": cap1},
                {"start": 5.0, "end": 9.8, "text": "수사관도 놓친 건조 사건"},
                {"start": 10.3, "end": 14.5, "text": "천 원 블록 소분 스펀지"},
                {"start": 14.6, "end": 17.2, "text": "원스윕 흡수 확인하세요"},
            ],
            "cta": {"type": "comment_engagement", "copy": "댓글로 확인하세요", "fact_ids": ["F01"]},
        }
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        return src_mp4, facts_md, spec_path
