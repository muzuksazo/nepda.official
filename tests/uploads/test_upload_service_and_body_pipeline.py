"""FR-009 & FR-011 · Presign auth, real ffprobe upload validation & multi-clip body pipeline tests."""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import unittest
import wave
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from app.store import JobStore  # noqa: E402
from app.tts_service import TTSAudioResult, WordTiming, measure_lufs  # noqa: E402
from app.upload_service import probe_video_metadata  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tests.support.production import _make_sample_mp4_bytes  # noqa: E402
from tests.support.projects_api import fake_google_verifier, login_client  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class _FakeTTSProvider:
    def synthesize(
        self,
        text: str,
        out_wav_path: Path,
        *,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSAudioResult:
        _ = (voice_id, speaking_rate)
        sr = 48000
        dur = 1.2
        n = int(round(dur * sr))
        out_wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            buf = bytearray()
            for i in range(n):
                val = int(round(32767.0 * 0.15 * math.sin(2.0 * math.pi * 330.0 * i / sr)))
                buf.extend(struct.pack("<h", val))
            wf.writeframes(bytes(buf))
        return TTSAudioResult(
            audio_path=out_wav_path,
            duration_sec=dur,
            words=[WordTiming(word=text[:4], start_sec=0.0, end_sec=dur)],
            provider="fake",
            voice_id="fake-kr",
            model_id="fake-model",
            cached=False,
        )


class TestUploadServiceAndBodyPipeline(unittest.TestCase):
    def test_presign_user_auth_real_probe_and_multi_clip_body_pipeline(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                google_client_id="dummy-client-id.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
                api_bearer_token="internal-worker-token",
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            job_store = JobStore(settings.db_path)
            proj_store = ProjectStore(settings.db_path)
            storage = LocalStorageBackend(Path(settings.work_root) / "_objects")
            app = create_app(
                settings=settings,
                store=job_store,
                project_store=proj_store,
                storage=storage,
                google_token_verifier=fake_google_verifier,
                tts_provider=_FakeTTSProvider(),
            )
            client = TestClient(app)

            # Unauthenticated presign blocked
            self.assertEqual(
                client.post("/v1/uploads/presign", json={"object_key": "uploads/a.mp4"}).status_code,
                401,
            )

            # End-user login allows presign (even when api_bearer_token is configured)
            login_client(client, "user-up:up@example.com")
            pre = client.post(
                "/v1/uploads/presign",
                json={"object_key": "uploads/user-up/p1/shot_01.mp4"},
            )
            self.assertEqual(pre.status_code, 200, pre.text)
            self.assertIn("upload_url", pre.json())

            # Cross-user upload prefix blocked
            cross = client.post(
                "/v1/uploads/presign",
                json={"object_key": "uploads/user-other/p1/shot_01.mp4"},
            )
            self.assertEqual(cross.status_code, 403)

            # Create project & upload 2 real clips (one horizontal 16:9, one vertical 9:16)
            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "스텐 물기제거 스퀴지",
                        "category": "living",
                        "verified_facts": ["실리콘 블레이드 밀착", "벽면 거치 훅 포함"],
                    },
                    "selected_types": ["C"],
                },
            ).json()["project_id"]

            clip1 = root / "clip1.mp4"
            clip2 = root / "clip2.mp4"
            clip1.write_bytes(_make_sample_mp4_bytes(duration=4.0, w=640, h=360, color="navy"))
            clip2.write_bytes(_make_sample_mp4_bytes(duration=4.5, w=360, h=640, color="darkred"))

            key1 = f"uploads/user-up/{pid}/shot_01.mp4"
            key2 = f"uploads/user-up/{pid}/shot_02.mp4"
            storage.upload_file(clip1, key1)
            storage.upload_file(clip2, key2)

            # Spoofed tiny duration in request must be overridden by real ffprobe duration (~8.5s total)
            comp = client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {"shot_no": 2, "object_key": key2, "duration_sec": 0.5, "width": 100, "height": 100},
                        {"shot_no": 1, "object_key": key1, "duration_sec": 0.5, "width": 100, "height": 100},
                    ]
                },
            )
            self.assertEqual(comp.status_code, 200, comp.text)
            cj = comp.json()
            self.assertEqual(cj["upload_status"], "WARNING")
            self.assertAlmostEqual(cj["total_duration_sec"], 8.5, delta=0.4)
            # Sorted by shot_no: shot 1 is 640x360 -> blur-bleed, shot 2 is 360x640 -> full-bleed
            self.assertEqual(cj["metadata"][0]["shot_no"], 1)
            self.assertEqual(cj["metadata"][0]["recommended_framing"], "blur-bleed")
            self.assertEqual(cj["metadata"][1]["shot_no"], 2)
            self.assertEqual(cj["metadata"][1]["recommended_framing"], "full-bleed")

            # Build standalone body.mp4 + body.srt (FR-009 separate track)
            body_resp = client.post(
                f"/v1/projects/{pid}/body",
                json={"target_duration_sec": 7.0, "tts_enabled": True, "burn_captions": True},
            )
            self.assertEqual(body_resp.status_code, 200, body_resp.text)
            bj = body_resp.json()
            self.assertEqual(bj["clip_count"], 2)
            self.assertEqual(bj["width"], 1080)
            self.assertEqual(bj["height"], 1920)
            self.assertAlmostEqual(bj["fps"], 30.0, delta=0.2)
            self.assertGreaterEqual(bj["duration_sec"], 6.8)
            self.assertTrue(bj["body_video_url"].startswith("/v1/media/"))
            self.assertTrue(bj["body_srt_url"].startswith("/v1/media/"))

            # Verify actual MP4 file via ffprobe + ebur128
            local_body_mp4 = storage.resolve_local_path(bj["object_keys"]["body_video"])
            self.assertIsNotNone(local_body_mp4)
            meta = probe_video_metadata(str(local_body_mp4))
            self.assertEqual(meta["width"], 1080)
            self.assertEqual(meta["height"], 1920)
            self.assertTrue(meta["has_audio"])
            lufs = measure_lufs(local_body_mp4)  # type: ignore[arg-type]
            self.assertIsNotNone(lufs)
            self.assertAlmostEqual(float(lufs), -14.0, delta=2.0)

            # Verify SRT content via streaming endpoint
            srt_dl = client.get(bj["body_srt_url"])
            self.assertEqual(srt_dl.status_code, 200)
            self.assertIn("-->", srt_dl.text)

            # GET /body returns saved manifest
            get_body = client.get(f"/v1/projects/{pid}/body")
            self.assertEqual(get_body.status_code, 200)
            self.assertEqual(get_body.json()["body_id"], bj["body_id"])

    def test_strict_upload_object_exists_rejects_missing_file(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                google_client_id="dummy-client-id.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
                require_uploaded_object_exists=True,
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            app = create_app(
                settings=settings,
                google_token_verifier=fake_google_verifier,
            )
            client = TestClient(app)
            login_client(client)

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {"name": "테스트 제품", "category": "living"},
                    "selected_types": ["A"],
                },
            ).json()["project_id"]

            bad = client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/nonexistent.mp4",
                            "duration_sec": 10.0,
                            "width": 1080,
                            "height": 1920,
                        }
                    ]
                },
            )
            self.assertEqual(bad.status_code, 400)
            self.assertEqual(bad.json()["detail"]["error"]["code"], "INVALID_UPLOAD_MEDIA")
