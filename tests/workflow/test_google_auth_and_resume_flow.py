"""FR-008·012·014 · Google One Tap auth, cross-device resume isolation, skip_drafts & deliverables tests."""

import time
import unittest
from datetime import datetime
from pathlib import Path

from tests.support.production import _make_sample_mp4_bytes
from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory


class TestGoogleAuthAndResumeFlow(unittest.TestCase):
    def test_google_one_tap_resume_isolation_and_deliverables(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            src_mp4 = root / "sample.mp4"
            src_mp4.write_bytes(_make_sample_mp4_bytes(duration=7.0, w=1080, h=1920))

            client = build_test_client(root)

            # Unauthenticated access blocked
            self.assertEqual(client.get("/v1/projects").status_code, 401)

            # Invalid Google ID token blocked
            bad = client.post("/v1/auth/google", json={"credential": "bad-token"})
            self.assertEqual(bad.status_code, 401)

            # User 1 logs in via Google One Tap
            token1 = login_client(client, "google-u1:u1@example.com")
            me = client.get("/v1/auth/me")
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["user"]["email"], "u1@example.com")

            # Create project & verify 7-day expires_at TTL
            created = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "다용도 물기 스펀지",
                        "category": "living",
                        "verified_facts": ["소분해서 틈새 물기 흡수"],
                    },
                    "selected_types": ["A"],
                    "flow_mode": "skip_drafts",
                },
            ).json()
            pid = created["project_id"]
            exp = datetime.fromisoformat(created["expires_at"])
            crt = datetime.fromisoformat(created["created_at"])
            self.assertAlmostEqual((exp - crt).total_seconds(), 7 * 86400, delta=10)

            # Upload real synthetic video & render dry_run=True via skip_drafts (FR-005)
            up = client.post(
                f"/v1/projects/{pid}/uploads/complete",
                json={
                    "clips": [
                        {
                            "shot_no": 1,
                            "object_key": "uploads/sample.mp4",
                            "local_path": str(src_mp4),
                        }
                    ]
                },
            )
            self.assertEqual(up.status_code, 200, up.text)

            ren = client.post(
                f"/v1/projects/{pid}/renders",
                json={"skip_drafts": True, "selected_type": "A", "dry_run": True},
            )
            self.assertEqual(ren.status_code, 202, ren.text)
            jid = ren.json()["job_id"]

            for _ in range(80):
                job = client.get(f"/v1/jobs/{jid}").json()
                if job["status"] in {"DRY_RUN_READY", "QC_READY", "FAILED"}:
                    break
                time.sleep(0.1)

            deliv = client.get(f"/v1/projects/{pid}/deliverables")
            self.assertEqual(deliv.status_code, 200, deliv.text)
            d_json = deliv.json()
            self.assertEqual(d_json["status"], "DRY_RUN_READY")
            self.assertTrue(d_json["ai_disclosure"]["has_ai_generated_media"])
            self.assertEqual(d_json["ai_disclosure"]["label_text"], "AI 연출 포함")
            self.assertEqual(d_json["expires_at"], created["expires_at"])

            # User 2 cannot access User 1's project; User 1 can still resume via Bearer token after logout
            client.post("/v1/auth/logout")
            self.assertEqual(client.get(f"/v1/projects/{pid}").status_code, 401)
            login_client(client, "google-u2:u2@example.com")
            self.assertEqual(client.get(f"/v1/projects/{pid}").status_code, 404)

            # User 1 resumes with token1 (simulating return after shooting on phone)
            resumed = client.get(
                f"/v1/projects/{pid}",
                headers={"Authorization": f"Bearer {token1}"},
            )
            self.assertEqual(resumed.status_code, 200)
            self.assertEqual(resumed.json()["latest_job_id"], jid)

    def test_cors_headers_and_logout_cookie_clearing(self) -> None:
        with temporary_directory() as td:
            client = build_test_client(Path(td))

            preflight = client.options(
                "/v1/auth/google",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            self.assertEqual(preflight.status_code, 200)
            self.assertEqual(
                preflight.headers.get("access-control-allow-origin"),
                "http://localhost:5173",
            )
            self.assertEqual(
                preflight.headers.get("access-control-allow-credentials"),
                "true",
            )

            login_resp = client.post(
                "/v1/auth/google",
                json={"credential": "google-cors:cors@example.com"},
                headers={"Origin": "http://localhost:5173"},
            )
            self.assertEqual(login_resp.status_code, 200)
            set_cookie = login_resp.headers.get("set-cookie", "")
            self.assertIn("napda_session=", set_cookie)
            self.assertIn("HttpOnly", set_cookie)
            self.assertIn("Path=/", set_cookie)
            self.assertEqual(
                login_resp.headers.get("access-control-allow-origin"),
                "http://localhost:5173",
            )

            logout_resp = client.post("/v1/auth/logout")
            self.assertEqual(logout_resp.status_code, 204)
            clear_cookie = logout_resp.headers.get("set-cookie", "")
            self.assertIn("napda_session=", clear_cookie)
            self.assertIn("Max-Age=0", clear_cookie)
            self.assertEqual(client.get("/v1/auth/me").status_code, 401)

    def test_publish_project_and_community_videos_persistence(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            client = build_test_client(root)

            # Empty community feed before any project is published
            empty = client.get("/v1/community/videos")
            self.assertEqual(empty.status_code, 200, empty.text)
            self.assertEqual(empty.json()["items"], [])

            login_client(client, "pub-u1:pub@example.com")
            created = client.post(
                "/v1/projects",
                json={
                    "product": {
                        "name": "초흡수 PVA 물걸레 스펀지",
                        "category": "living",
                        "verified_facts": ["3초 만에 물기 순삭"],
                    },
                    "selected_types": ["A"],
                },
            ).json()
            pid = created["project_id"]
            self.assertFalse(created["is_public"])

            # Publish project to community
            pub = client.patch(
                f"/v1/projects/{pid}/publish",
                json={"is_public": True, "caption": "3초 만에 물기 순삭"},
            )
            self.assertEqual(pub.status_code, 200, pub.text)
            self.assertEqual(
                pub.json(),
                {"project_id": pid, "is_public": True, "caption": "3초 만에 물기 순삭"},
            )

            # Persisted in ProjectSummary & ProjectDetailResponse
            listed = client.get("/v1/projects").json()["projects"]
            self.assertTrue(listed[0]["is_public"])
            detail = client.get(f"/v1/projects/{pid}").json()
            self.assertTrue(detail["is_public"])
            self.assertEqual(detail["public_caption"], "3초 만에 물기 순삭")

            # Visible in public GET /v1/community/videos (with hook_type filtering)
            feed_all = client.get("/v1/community/videos")
            self.assertEqual(feed_all.status_code, 200, feed_all.text)
            items = feed_all.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["project_id"], pid)
            self.assertEqual(items[0]["hook_type"], "A")
            self.assertEqual(items[0]["product_name"], "초흡수 PVA 물걸레 스펀지")
            self.assertEqual(items[0]["caption"], "3초 만에 물기 순삭")
            self.assertEqual(items[0]["creator_name"], "테스트 셀러")

            self.assertEqual(len(client.get("/v1/community/videos?hook_type=A").json()["items"]), 1)
            self.assertEqual(len(client.get("/v1/community/videos?hook_type=B").json()["items"]), 0)

            # Unpublishing removes it from community feed
            unpub = client.patch(
                f"/v1/projects/{pid}/publish",
                json={"is_public": False},
            )
            self.assertEqual(unpub.status_code, 200, unpub.text)
            self.assertFalse(unpub.json()["is_public"])
            self.assertEqual(client.get("/v1/community/videos").json()["items"], [])
