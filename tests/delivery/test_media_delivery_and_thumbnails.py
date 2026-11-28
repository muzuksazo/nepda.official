"""FR-012 & FR-013 · Signed media Range streaming, S3 re-signing & automated cover thumbnails."""

from __future__ import annotations

import subprocess
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
            self.assertEqual(dj["thumbnail"]["style"], "invert-box")
            self.assertGreaterEqual(len(dj["thumbnail"]["candidate_keys"]), 1)
            self.assertEqual(
                len(dj["thumbnail"]["candidate_image_urls"]),
                len(dj["thumbnail"]["candidate_keys"]),
            )
            style_previews = dj["thumbnail"]["style_previews"]
            self.assertEqual(
                set(style_previews.keys()),
                {"invert-box", "white-label", "serif-outline", "pov-bar"},
            )
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

            # Explicit custom thumbnail regeneration + legacy alias mapping to 4 Figma SSOT styles
            custom = client.post(
                f"/v1/projects/{pid}/thumbnail",
                json={
                    "headline_lines": ["타이머 고르기 전", "이것만 보세요"],
                    "badge": "실물 확인",
                    "highlight_word": "이것만",
                    "style": "line_blocks",
                },
            )
            self.assertEqual(custom.status_code, 200, custom.text)
            cj = custom.json()
            self.assertTrue(cj["safe_zone_1_1_ok"])
            self.assertEqual(cj["style"], "white-label")
            self.assertEqual(cj["highlight_word"], "이것만")
            self.assertEqual(cj["headline_lines"], ["타이머 고르기 전", "이것만 보세요"])
            self.assertGreaterEqual(len(cj["candidate_image_urls"]), 1)
            self.assertEqual(
                set(cj["style_previews"].keys()),
                {"invert-box", "white-label", "serif-outline", "pov-bar"},
            )

            # Legacy alias mapping: stroke -> serif-outline, blocks -> white-label, card -> invert-box, split -> pov-bar
            for alias, canonical in (
                ("stroke", "serif-outline"),
                ("stroke_bold", "serif-outline"),
                ("blocks", "white-label"),
                ("card", "invert-box"),
                ("panel_card", "invert-box"),
                ("split", "pov-bar"),
            ):
                alias_resp = client.post(
                    f"/v1/projects/{pid}/thumbnail",
                    json={"headline_lines": ["3초 만에 물기 순삭"], "style": alias},
                )
                self.assertEqual(alias_resp.status_code, 200, (alias, alias_resp.text))
                self.assertEqual(alias_resp.json()["style"], canonical)

            # Deliverables reflects the latest selected style (pov-bar)
            deliv_after = client.get(f"/v1/projects/{pid}/deliverables").json()
            self.assertEqual(deliv_after["thumbnail"]["style"], "pov-bar")

            # R3 SSOT: all 4 canonical Figma styles render valid 1080x1920 safe-zone PNGs with highlight_word
            for figma_style in ("invert-box", "white-label", "serif-outline", "pov-bar"):
                f_resp = client.post(
                    f"/v1/projects/{pid}/thumbnail",
                    json={
                        "headline_lines": ["댐 균열 테이프 100겹", "버티는 건 딱 3초"],
                        "badge": "실험 검증",
                        "highlight_word": "100겹",
                        "style": figma_style,
                    },
                )
                self.assertEqual(f_resp.status_code, 200, (figma_style, f_resp.text))
                fj = f_resp.json()
                self.assertEqual(fj["style"], figma_style)
                self.assertTrue(fj["safe_zone_1_1_ok"], (figma_style, fj["warnings"]))
                self.assertIn(figma_style, fj["style_previews"])
                img_r = client.get(fj["image_url"])
                self.assertEqual(img_r.status_code, 200, figma_style)
                out_p = root / f"figma_{figma_style}.png"
                out_p.write_bytes(img_r.content)
                with Image.open(out_p) as im:
                    self.assertEqual(im.size, (1080, 1920))

    def test_prepend_thumbnail_to_video_and_no_double_prepend(self) -> None:
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

            src_mp4 = root / "master.mp4"
            src_mp4.write_bytes(_make_sample_mp4_bytes(duration=2.0, w=1080, h=1920))
            clean_mp4 = root / "clean.mp4"
            clean_mp4.write_bytes(_make_sample_mp4_bytes(duration=2.0, w=1080, h=1920))

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "방수 테이프",
                        "category": "living",
                        "verified_facts": ["초강력 방수", "3초 부착"],
                    },
                    "selected_types": ["A"],
                },
            ).json()["project_id"]

            master_uri = storage.upload_file(src_mp4, f"projects/{pid}/renders/job_cov1/master.mp4")
            clean_uri = storage.upload_file(clean_mp4, f"projects/{pid}/renders/job_cov1/clean.mp4")
            job_store.create_job("job_cov1", pid, {}, status="QC_READY", stage="QC_READY")
            job_store.update_job(
                "job_cov1",
                status="QC_READY",
                stage="QC_READY",
                artifacts={
                    "rendered": [
                        {
                            "variant": "A",
                            "duration": 2.0,
                            "master_mp4": master_uri,
                            "clean_mp4": clean_uri,
                            "lufs": {"final_lufs": -14.0},
                        }
                    ]
                },
            )
            proj_store.update_project(pid, status="DELIVERABLE_READY", latest_job_id="job_cov1")

            deliv = client.get(f"/v1/projects/{pid}/deliverables")
            self.assertEqual(deliv.status_code, 200, deliv.text)
            dj = deliv.json()
            self.assertAlmostEqual(dj["video"]["duration_sec"], 2.4, places=2)
            vid_bytes_1 = client.get(dj["video"]["download_url"]).content
            clean_bytes = client.get(dj["video"]["clean_download_url"]).content
            self.assertEqual(clean_bytes, clean_mp4.read_bytes())

            # Regenerating thumbnail with another style must prepend from original master (never double-prepend)
            regen = client.post(
                f"/v1/projects/{pid}/thumbnail",
                json={"headline_lines": ["3초 만에 누수 끝"], "style": "white-label"},
            )
            self.assertEqual(regen.status_code, 200, regen.text)
            deliv2 = client.get(f"/v1/projects/{pid}/deliverables").json()
            self.assertAlmostEqual(deliv2["video"]["duration_sec"], 2.4, places=2)
            vid2_path = root / "out_after_regen.mp4"
            vid2_path.write_bytes(client.get(deliv2["video"]["download_url"]).content)
            self.assertGreater(len(vid_bytes_1), 1000)

            ffprobe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(vid2_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            actual_dur = float(ffprobe.stdout.strip())
            self.assertAlmostEqual(actual_dur, 2.4, delta=0.15)

    def test_figma_four_styles_horizontal_autofit_long_24_char_korean(self) -> None:
        from tests.support.media_tools import ad_thumbnail_builder
        import json

        with temporary_directory() as td:
            root = Path(td)
            bg = root / "bg.png"
            Image.new("RGB", (1080, 1920), (42, 72, 110)).save(bg)
            long_24 = "초흡수물걸레스펀지로바닥물기삼초만에완전순삭하기"
            self.assertEqual(len(long_24), 24)

            spec = {
                "canvas": {"width": 1080, "height": 1920},
                "strict_margin": True,
                "thumbnails": [
                    {
                        "id": st,
                        "filename": f"{st}.png",
                        "layout": "figma",
                        "figma_variant": st,
                        "image": str(bg),
                        "badge": "실물 검증 테스트",
                        "highlight_word": "삼초만에",
                        "headline": {
                            "style": st,
                            "lines": [
                                {"text": long_24},
                                {"text": "두번째줄도안전영역안에완벽하게자동축소"},
                            ],
                        },
                    }
                    for st in ("invert-box", "white-label", "serif-outline", "pov-bar")
                ],
            }
            spec_path = root / "figma_long_spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            res = ad_thumbnail_builder.build_from_spec(str(spec_path), str(root / "out"))
            self.assertEqual(res["count"], 4)
            self.assertTrue(res["all_safe_zone_ok"], res["thumbnails"])
            for info in res["thumbnails"]:
                self.assertTrue(info["safe_zone_ok"], (info["id"], info["warnings"]))
                hb = info["bounds"]["headline"]
                self.assertGreaterEqual(hb[0], 63, info)
                self.assertLessEqual(hb[2], 1016, info)
                self.assertGreaterEqual(hb[1], 240, info)
                self.assertLessEqual(hb[3], 1396, info)
                with Image.open(info["path"]) as im:
                    self.assertEqual(im.size, (1080, 1920))

    def test_thumbnail_service_prefers_clean_mp4_over_master_mp4(self) -> None:
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

            clean_mp4 = root / "clean.mp4"
            master_mp4 = root / "master.mp4"
            # Distinct solid colors: green for clean_mp4, red for master_mp4
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x10C840:s=1080x1920:d=2:r=24",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clean_mp4),
                ],
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0xE02020:s=1080x1920:d=2:r=24",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(master_mp4),
                ],
                capture_output=True,
                check=True,
            )

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {"name": "초흡수 스펀지", "category": "living", "verified_facts": ["물기 순삭"]},
                    "selected_types": ["A"],
                },
            ).json()["project_id"]

            clean_uri = storage.upload_file(clean_mp4, f"projects/{pid}/renders/job_cln/clean.mp4")
            master_uri = storage.upload_file(master_mp4, f"projects/{pid}/renders/job_cln/master.mp4")
            job_store.create_job("job_cln", pid, {}, status="QC_READY", stage="QC_READY")
            job_store.update_job(
                "job_cln",
                status="QC_READY",
                stage="QC_READY",
                artifacts={"rendered": [{"variant": "A", "duration": 2.0, "master_mp4": master_uri, "clean_mp4": clean_uri}]},
            )
            proj_store.update_project(pid, status="RENDERING", latest_job_id="job_cln")

            deliv = client.get(f"/v1/projects/{pid}/deliverables")
            self.assertEqual(deliv.status_code, 200, deliv.text)
            cand_urls = deliv.json()["thumbnail"]["candidate_image_urls"]
            self.assertGreaterEqual(len(cand_urls), 1)
            kf_resp = client.get(cand_urls[0])
            self.assertEqual(kf_resp.status_code, 200)
            kf_path = root / "kf0.png"
            kf_path.write_bytes(kf_resp.content)
            with Image.open(kf_path) as im:
                r, g, b = im.convert("RGB").getpixel((540, 960))
                # Green dominant -> extracted from clean_mp4, NOT red master_mp4!
                self.assertGreater(g, r + 60, f"Expected clean green frame, got RGB=({r},{g},{b})")

    def test_upload_rendered_discovers_sibling_clean_mp4(self) -> None:
        from app.pipeline import ProductionPipeline

        with temporary_directory() as td:
            root = Path(td)
            settings = Settings(
                _env_file=None,
                work_root=str(root / "work"),
                output_dir=str(root / "outputs"),
                db_path=str(root / "napda.db"),
            )
            storage = LocalStorageBackend(root / "objects")
            pipeline = ProductionPipeline(settings, JobStore(settings.db_path), storage=storage)

            final_dir = root / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            mp4 = final_dir / "napda_test_A.mp4"
            clean = final_dir / "napda_test_A_clean.mp4"
            mp4.write_bytes(b"master-bytes")
            clean.write_bytes(b"clean-bytes")

            uploaded = pipeline._upload_rendered(
                {"rendered": [{"variant": "A", "mp4": str(mp4), "duration": 10.0}]},
                "prj_1",
                "job_1",
            )
            self.assertEqual(len(uploaded), 1)
            self.assertIn("master_mp4", uploaded[0])
            self.assertIn("clean_mp4", uploaded[0])
            self.assertTrue(uploaded[0]["clean_mp4"].endswith("napda_test_A_clean.mp4"))
