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

PROD_ROOT = Path(__file__).resolve().parents[1]
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


class TestGenAIClientFactory(unittest.TestCase):
    def test_build_client_ai_studio_vs_vertex_ai(self) -> None:
        with patch("app.genai_provider.genai.Client") as m_client:
            s_key = Settings(gemini_api_key="AIzaDummyKey", google_genai_use_vertexai=False)
            build_genai_client(s_key)
            m_client.assert_called_once_with(api_key="AIzaDummyKey")

        with patch("app.genai_provider.genai.Client") as m_client:
            s_vtx = Settings(
                google_genai_use_vertexai=True,
                google_cloud_project="my-gcp-proj",
                google_cloud_location="us-central1",
            )
            build_genai_client(s_vtx)
            m_client.assert_called_once_with(
                vertexai=True,
                project="my-gcp-proj",
                location="us-central1",
            )

        with self.assertRaises(ValueError):
            build_genai_client(Settings(gemini_api_key=None, google_genai_use_vertexai=False))
        with self.assertRaises(ValueError):
            build_genai_client(Settings(google_genai_use_vertexai=True, google_cloud_project=None))


class TestGenAIMediaProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.png_bytes = _make_sample_png_bytes()
        cls.mp4_bytes = _make_sample_mp4_bytes(duration=2.0)

    def test_image_video_polling_and_tts_wav_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            anchor = Path(td) / "anchor.png"
            anchor.write_bytes(self.png_bytes)

            fake_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=_FakeModels(return_wav=False),
            )
            settings = Settings(gemini_api_key="dummy", poll_interval_sec=0.0, video_timeout_sec=10.0)
            provider = GenAIMediaProvider(settings, client=fake_client)

            ref_path = Path(td) / "refs" / "R_A1.png"
            r1 = provider.generate_reference_image(
                "Noir office desk, zero readable text.",
                ref_path,
                anchor_paths=[anchor],
            )
            self.assertFalse(r1.skipped)
            self.assertTrue(ref_path.exists())
            # input list should include text + anchor image
            img_call = fake_client.interactions.created[0]
            self.assertEqual(img_call["model"], "gemini-nano-banana-2.1")
            self.assertEqual(img_call["response_format"]["aspect_ratio"], "9:16")
            self.assertEqual(len(img_call["input"]), 2)

            # Second call should hit idempotency cache without calling API again
            r2 = provider.generate_reference_image("prompt", ref_path, skip_existing=True)
            self.assertTrue(r2.skipped)
            self.assertEqual(len(fake_client.interactions.created), 1)

            # Background video polling
            vid_path = Path(td) / "clips" / "G_A1.mp4"
            v1 = provider.generate_video_clip(
                "Camera pushes toward wet bathroom tiles, zero readable text.",
                vid_path,
                duration_sec=5,
                resolution="720p",
                reference_paths=[ref_path],
                sleep_fn=lambda _: None,
            )
            self.assertFalse(v1.skipped)
            self.assertTrue(vid_path.exists())
            vid_call = fake_client.interactions.created[1]
            self.assertTrue(vid_call["background"])
            self.assertEqual(vid_call["response_format"]["duration"], "5s")

            # Failed status raises loudly
            fail_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes, fail_video=True),
                models=_FakeModels(),
            )
            fail_provider = GenAIMediaProvider(settings, client=fail_client)
            with self.assertRaises(RuntimeError):
                fail_provider.generate_video_clip(
                    "prompt",
                    Path(td) / "clips" / "fail.mp4",
                    sleep_fn=lambda _: None,
                )

            # Raw PCM L16 TTS gets wrapped into a valid WAV container
            tts_path = Path(td) / "audio" / "beat_01.wav"
            t_res = provider.generate_tts_beat("형사님, 현장에 물 흔적이 사라졌습니다.", tts_path)
            self.assertGreater(t_res.bytes_written, 44)
            with wave.open(str(tts_path), "rb") as wf:
                self.assertEqual(wf.getframerate(), 24000)
                self.assertEqual(wf.getnchannels(), 1)
                self.assertGreater(wf.getnframes(), 1000)

    def test_execute_jobs_budget_cap_and_surgical_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            jobs_file = proj / "05_jobs.json"
            jobs_payload = {
                "project_id": "test-jobs",
                "aspect_ratio": "9:16",
                "resolution": "720p",
                "anchors": [],
                "references": [
                    {
                        "id": "R_A1",
                        "file": "refs/R_A1.png",
                        "prompt": "One dark noir studio desk, zero readable text.",
                        "settings": {"aspect_ratio": "9:16"},
                    }
                ],
                "units": [
                    {
                        "id": "G_A1",
                        "reference_ids": ["R_A1"],
                        "settings": {"aspect_ratio": "9:16", "resolution": "720p", "duration_sec": 5},
                        "est_credits": 15,
                        "outputs": ["clips/G_A1_t1.mp4"],
                        "prompt": "Smooth slow push-in, zero readable text.",
                    },
                    {
                        "id": "G_A2",
                        "reference_ids": ["R_A1"],
                        "settings": {"aspect_ratio": "9:16", "resolution": "720p", "duration_sec": 5},
                        "est_credits": 15,
                        "outputs": ["clips/G_A2_t1.mp4"],
                        "prompt": "Static medium framing, zero readable text.",
                    },
                ],
            }
            jobs_file.write_text(json.dumps(jobs_payload), encoding="utf-8")

            fake_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=_FakeModels(),
            )
            settings = Settings(gemini_api_key="dummy", poll_interval_sec=0.0, video_timeout_sec=10.0)
            provider = GenAIMediaProvider(settings, client=fake_client)

            # Budget cap triggers BEFORE any paid video calls
            with self.assertRaises(BudgetExceededError):
                execute_jobs_file(jobs_file, proj, provider, max_credits=20)
            video_calls = [
                c for c in fake_client.interactions.created if c.get("response_format", {}).get("type") == "video"
            ]
            self.assertEqual(len(video_calls), 0)

            # Now run within budget
            rep = execute_jobs_file(jobs_file, proj, provider, concurrency=2, max_credits=50)
            self.assertEqual(rep["total_est_credits"], 30)
            self.assertEqual(len(rep["units"]), 2)
            self.assertTrue((proj / "clips" / "G_A1_t1.mp4").exists())
            self.assertTrue((proj / "generation_report.json").exists())

            # Surgical retry of G_A2 only
            rep_retry = execute_jobs_file(
                jobs_file, proj, provider, skip_existing=False, only_unit_ids=["G_A2"]
            )
            self.assertEqual([u["id"] for u in rep_retry["units"]], ["G_A2"])


class TestProductionPipelineAndAPI(unittest.TestCase):
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

    def test_end_to_end_pipeline_gate_a_render_and_reskin_block(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            settings = Settings(
                gemini_api_key="dummy",
                work_root=str(root / "work"),
                db_path=str(root / "jobs.db"),
                poll_interval_sec=0.0,
            )
            store = JobStore(settings.db_path)
            fake_client = SimpleNamespace(
                interactions=_FakeInteractions(png_bytes=self.png_bytes, mp4_bytes=self.mp4_bytes),
                models=_FakeModels(return_wav=True),
            )
            provider = GenAIMediaProvider(settings, client=fake_client)
            pipeline = ProductionPipeline(settings, store, provider_factory=lambda _: provider)

            # 1) Bad spec blocked BEFORE paid calls
            bad_dir = root / "bad"
            bad_dir.mkdir()
            bad_src, bad_facts, bad_spec = self._write_valid_campaign_inputs(bad_dir, bad_c_hook=True)
            with self.assertRaises(LintFailedError):
                pipeline.run_campaign(
                    CampaignRequest(
                        campaign_id="bad-camp",
                        source_video=str(bad_src),
                        facts_path=str(bad_facts),
                        spec_path=str(bad_spec),
                    )
                )
            self.assertEqual(len(fake_client.interactions.created), 0)

            # 2) Valid campaign renders real MP4 + SRT + QA strip + records archetype
            good_dir = root / "good"
            good_dir.mkdir()
            src1, facts1, spec1 = self._write_valid_campaign_inputs(good_dir, a_genre="noir_interrogation")
            res = pipeline.run_campaign(
                CampaignRequest(
                    campaign_id="good-camp-1",
                    source_video=str(src1),
                    facts_path=str(facts1),
                    spec_path=str(spec1),
                )
            )
            self.assertEqual(res["status"], "QC_READY")
            rendered = res["artifacts"]["rendered"][0]
            self.assertTrue(rendered["master_mp4"].startswith("file://"))
            master_file = Path(rendered["master_mp4"].replace("file://", ""))
            self.assertTrue(master_file.exists())
            self.assertGreater(master_file.stat().st_size, 10_000)

            # 3) Second campaign reusing identical a_genre_archetype is blocked by --compare-campaigns
            reskin_dir = root / "reskin"
            reskin_dir.mkdir()
            src2, facts2, spec2 = self._write_valid_campaign_inputs(reskin_dir, a_genre="noir_interrogation")
            with self.assertRaises(LintFailedError):
                pipeline.run_campaign(
                    CampaignRequest(
                        campaign_id="good-camp-2",
                        source_video=str(src2),
                        facts_path=str(facts2),
                        spec_path=str(spec2),
                    )
                )

    def test_fastapi_endpoints_and_bearer_auth(self) -> None:
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            settings = Settings(
                gemini_api_key="dummy",
                api_bearer_token="secret-token-123",
                work_root=str(root / "work"),
                db_path=str(root / "jobs.db"),
            )
            app = create_app(settings=settings)
            client = TestClient(app)

            h = client.get("/health")
            self.assertEqual(h.status_code, 200)
            self.assertEqual(h.json()["status"], "ok")
            self.assertEqual(h.json()["auth_mode"], "ai_studio")

            # Auth guard blocks unauthenticated requests
            unauth = client.get("/v1/jobs")
            self.assertEqual(unauth.status_code, 401)

            in_dir = root / "inputs"
            in_dir.mkdir()
            src, facts, spec = self._write_valid_campaign_inputs(in_dir, a_genre="romance_breakup")

            headers = {"Authorization": "Bearer secret-token-123"}
            post = client.post(
                "/v1/jobs",
                headers=headers,
                json={
                    "campaign_id": "api-dry-run",
                    "source_video": str(src),
                    "facts_path": str(facts),
                    "spec_path": str(spec),
                    "dry_run": True,
                },
            )
            self.assertEqual(post.status_code, 202, post.text)
            jid = post.json()["job_id"]

            final_job = None
            for _ in range(80):
                g = client.get(f"/v1/jobs/{jid}", headers=headers)
                self.assertEqual(g.status_code, 200)
                final_job = g.json()
                if final_job["status"] in {"DRY_RUN_READY", "QC_READY", "FAILED"}:
                    break
                time.sleep(0.1)

            self.assertIsNotNone(final_job)
            self.assertEqual(final_job["status"], "DRY_RUN_READY", final_job)
            self.assertTrue(final_job["lint"]["passed"])


if __name__ == "__main__":
    unittest.main()
