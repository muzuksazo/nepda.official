"""FR-012 & FR-013 · Signed media Range streaming, S3 re-signing & automated cover thumbnails."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.media_delivery import issue_media_token, resolve_media_url, verify_media_token  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from app.store import JobStore  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tests.support.production import _make_sample_mp4_bytes  # noqa: E402
from tests.support.projects_api import build_test_client, fake_google_verifier, login_client  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class _FakeS3Storage:
    def presign_download(self, object_key: str, expires_sec: int = 3600) -> str:
        return f"https://r2.example.com/signed/{object_key}?exp={expires_sec}"


class TestMediaDeliveryAndThumbnails(unittest.TestCase):
    def test_signed_media_range_streaming_and_tamper_rejection(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            client = build_test_client(root)
            login_client(client)

            storage = client.app.state.storage  # type: ignore[attr-defined]
            settings = client.app.state.settings  # type: ignore[attr-defined]

            sample_mp4 = root / "clip.mp4"
            raw_bytes = _make_sample_mp4_bytes(duration=2.0, w=720, h=1280)
            sample_mp4.write_bytes(raw_bytes)
            uri = storage.upload_file(sample_mp4, "projects/p1/renders/j1/master.mp4")

            stream_url = resolve_media_url(uri, storage=storage, settings=settings)
            dl_url = resolve_media_url(
                uri, storage=storage, settings=settings, download=True, filename="napda_final.mp4"
            )
            self.assertIsNotNone(stream_url)
            self.assertTrue(stream_url.startswith("/v1/media/"))
            self.assertTrue(dl_url.endswith("?download=1"))

            # Full GET 200
            full = client.get(stream_url)
            self.assertEqual(full.status_code, 200)
            self.assertEqual(full.headers.get("accept-ranges"), "bytes")
            self.assertEqual(full.content, raw_bytes)

            # Byte-range 206 Partial Content
            part = client.get(stream_url, headers={"Range": "bytes=0-127"})
            self.assertEqual(part.status_code, 206)
            self.assertEqual(part.headers.get("content-range"), f"bytes 0-127/{len(raw_bytes)}")
            self.assertEqual(part.content, raw_bytes[:128])

            # Download disposition
            dl = client.get(dl_url)
            self.assertEqual(dl.status_code, 200)
            self.assertIn("attachment;", dl.headers.get("content-disposition", ""))

            # Tampered or expired tokens are rejected
            self.assertEqual(client.get("/v1/media/tampered.token").status_code, 403)
            expired_tok = issue_media_token(
                "projects/p1/renders/j1/master.mp4",
                settings.session_secret,
                ttl_sec=10,
                now_epoch=1000,
            )
            with self.assertRaises(ValueError):
                verify_media_token(expired_tok, settings.session_secret, now_epoch=2000)

            # S3 mode re-signs dynamically per query
            s3_settings = Settings(_env_file=None, storage_backend="s3", s3_bucket="b")
            s3_url = resolve_media_url(
                "projects/p1/renders/j1/master.mp4",
                storage=_FakeS3Storage(),  # type: ignore[arg-type]
                settings=s3_settings,
            )
            self.assertEqual(
                s3_url,
                "https://r2.example.com/signed/projects/p1/renders/j1/master.mp4?exp=3600",
            )

    def test_thumbnail_endpoint_and_deliverables_auto_thumbnail(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                gemini_api_key="dummy-key",
                google_client_id="dummy-client-id.apps.googleusercontent.com",
                session_secret="test-session-secret-32bytes-minimum",
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
            )
            client = TestClient(app)
            login_client(client)

            # Create project & upload sample video
            src_mp4 = root / "sample.mp4"
            src_mp4.write_bytes(_make_sample_mp4_bytes(duration=6.0, w=1080, h=1920))
            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "마그네틱 주방 타이머",
                        "category": "kitchen",
                        "verified_facts": ["대형 LED 숫자 표시", "강력 자석 부착"],
                    },
                    "selected_types": ["C"],
                },
            ).json()["project_id"]

            # Simulate QC_READY job without pre-built thumbnails (like hookpipe/renders)
            master_uri = storage.upload_file(src_mp4, f"projects/{pid}/renders/job_qc1/master.mp4")
            job_store.create_job("job_qc1", pid, {}, status="QC_READY", stage="QC_READY")
            job_store.update_job(
                "job_qc1",
                status="QC_READY",
                stage="QC_READY",
                artifacts={
                    "rendered": [
                        {
                            "variant": "C",
                            "duration": 16.0,
                            "master_mp4": master_uri,
                            "lufs": {"final_lufs": -14.0},
                        }
                    ]
                },
            )
            proj_store.update_project(pid, status="RENDERING", latest_job_id="job_qc1")

            deliv = client.get(f"/v1/projects/{pid}/deliverables")
            self.assertEqual(deliv.status_code, 200, deliv.text)
            dj = deliv.json()
            self.assertTrue(dj["video"]["stream_url"].startswith("/v1/media/"))
            self.assertIsNotNone(dj["thumbnail"])
            self.assertTrue(dj["thumbnail"]["safe_zone_1_1_ok"])
            self.assertGreaterEqual(len(dj["thumbnail"]["headline_lines"]), 1)
            self.assertEqual(dj["thumbnail"]["style"], "stroke_bold")
            self.assertGreaterEqual(len(dj["thumbnail"]["candidate_keys"]), 1)
            self.assertEqual(
                len(dj["thumbnail"]["candidate_image_urls"]),
                len(dj["thumbnail"]["candidate_keys"]),
            )
            style_previews = dj["thumbnail"]["style_previews"]
            self.assertEqual(set(style_previews.keys()), {"stroke_bold", "line_blocks", "panel_card"})
            for st_name, prev_url in style_previews.items():
                self.assertTrue(prev_url.startswith("/v1/media/"), (st_name, prev_url))
                prev_resp = client.get(prev_url)
                self.assertEqual(prev_resp.status_code, 200, st_name)
                self.assertGreater(len(prev_resp.content), 10_000, st_name)
                p_file = root / f"preview_{st_name}.png"
                p_file.write_bytes(prev_resp.content)
                with Image.open(p_file) as im:
                    self.assertEqual(im.size, (1080, 1920))

            # BUG-07: ProjectSummary.thumbnail_url is populated with signed URL once thumbnail exists
            listed = client.get("/v1/projects")
            self.assertEqual(listed.status_code, 200, listed.text)
            summary = next(p for p in listed.json()["projects"] if p["project_id"] == pid)
            self.assertIsNotNone(summary["thumbnail_url"])
            self.assertTrue(summary["thumbnail_url"].startswith("/v1/media/"))
            self.assertEqual(client.get(summary["thumbnail_url"]).status_code, 200)

            img_resp = client.get(dj["thumbnail"]["image_url"])
            self.assertEqual(img_resp.status_code, 200)
            cover_file = root / "fetched_cover.png"
            cover_file.write_bytes(img_resp.content)
            with Image.open(cover_file) as im:
                self.assertEqual(im.size, (1080, 1920))

            # Explicit custom thumbnail regeneration + style alias support
            custom = client.post(
                f"/v1/projects/{pid}/thumbnail",
                json={
                    "headline_lines": ["타이머 고르기 전", "이것만 보세요"],
                    "badge": "실물 확인",
                    "style": "line_blocks",
                },
            )
            self.assertEqual(custom.status_code, 200, custom.text)
            cj = custom.json()
            self.assertTrue(cj["safe_zone_1_1_ok"])
            self.assertEqual(cj["style"], "line_blocks")
            self.assertEqual(cj["headline_lines"], ["타이머 고르기 전", "이것만 보세요"])
            self.assertGreaterEqual(len(cj["candidate_image_urls"]), 1)
            self.assertEqual(
                set(cj["style_previews"].keys()),
                {"stroke_bold", "line_blocks", "panel_card"},
            )

            # Alias mapping: stroke -> stroke_bold, blocks -> line_blocks, card -> panel_card
            for alias, canonical in (("stroke", "stroke_bold"), ("blocks", "line_blocks"), ("card", "panel_card")):
                alias_resp = client.post(
                    f"/v1/projects/{pid}/thumbnail",
                    json={"headline_lines": ["3초 만에 물기 순삭"], "style": alias},
                )
                self.assertEqual(alias_resp.status_code, 200, alias_resp.text)
                self.assertEqual(alias_resp.json()["style"], canonical)

            # Deliverables reflects the latest selected style (panel_card)
            deliv_after = client.get(f"/v1/projects/{pid}/deliverables").json()
            self.assertEqual(deliv_after["thumbnail"]["style"], "panel_card")
