"""Tests for Admin account management, internal credit/quota bypass, and immediate render cancellation."""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth import AuthenticatedUser, SESSION_COOKIE_NAME, issue_session_token  # noqa: E402
from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore, hydrate_internal_accounts_from_storage  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from tests.support.projects_api import (  # noqa: E402
    fake_google_verifier,
    fake_scenario_generator,
    fake_storyboard_generator,
)
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestAdminAccountsAndCancel(unittest.TestCase):
    def _setup_app(
        self,
        root: Path,
        *,
        daily_render_limit: int = 1,
        admin_emails: str = "admin@napda.io",
        api_bearer_token: str = "adm-secret",
    ):
        settings = Settings(
            _env_file=None,
            gemini_api_key="dummy-key",
            google_client_id="client-id",
            session_secret="test-session-secret-0123456789abcdef",
            admin_emails=admin_emails,
            api_bearer_token=api_bearer_token,
            hook_render_mode="dry_run",
            daily_render_limit=daily_render_limit,
            credits_per_video=12,
            initial_free_videos=0,
            work_root=str(root / "work"),
            output_dir=str(root / "outputs"),
            db_path=str(root / "napda.db"),
            min_upload_total_sec=5.0,
            max_upload_total_sec=90.0,
        )
        store = ProjectStore(settings.db_path)
        storage = LocalStorageBackend(root / "storage")
        app = create_app(
            settings,
            project_store=store,
            storage=storage,
            google_token_verifier=fake_google_verifier,
            scenario_generator=fake_scenario_generator,
            storyboard_generator=fake_storyboard_generator,
        )
        return app, settings, store, storage

    @staticmethod
    def _create_project_with_upload(client: TestClient) -> str:
        res = client.post(
            "/v1/projects",
            json={
                "product": {
                    "name": "내부 테스트 스펀지",
                    "category": "kitchen",
                    "verified_facts": ["스크래치 없는 부드러운 표면", "강한 물기 흡수력"],
                },
                "selected_types": ["A"],
            },
        )
        assert res.status_code == 201, res.text
        pid = res.json()["project_id"]

        scns = client.post(
            f"/v1/projects/{pid}/scenarios",
            json={"provider": "google", "count": 1},
        )
        assert scns.status_code == 200, scns.text
        sid = scns.json()["scenarios"][0]["scenario_id"]

        sel = client.post(f"/v1/projects/{pid}/scenarios/{sid}/select")
        assert sel.status_code == 200, sel.text

        up = client.post(
            f"/v1/projects/{pid}/uploads/complete",
            json={
                "clips": [
                    {
                        "shot_no": 1,
                        "object_key": f"uploads/u/{pid}/shot_01.mp4",
                        "duration_sec": 12.0,
                        "width": 1080,
                        "height": 1920,
                        "file_size_bytes": 1024,
                    }
                ]
            },
        )
        assert up.status_code == 200, up.text
        return pid

    def test_admin_internal_account_management_persistence_and_credit_bypass(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            app, settings, store, storage = self._setup_app(root, daily_render_limit=1)
            client = TestClient(app)

            # Unauthenticated admin call rejected
            unauth = client.get("/v1/admin/accounts")
            self.assertEqual(unauth.status_code, 401)

            # Pre-register an internal email via admin API before user even logs in
            admin_hdr = {"Authorization": f"Bearer {settings.api_bearer_token}"}
            reg = client.post(
                "/v1/admin/accounts/internal",
                headers=admin_hdr,
                json={"email": "QA-Tester@gmail.com", "is_internal": True, "note": "내부 QA"},
            )
            self.assertEqual(reg.status_code, 200, reg.text)
            reg_body = reg.json()
            self.assertEqual(reg_body["internal_count"], 1)
            self.assertEqual(reg_body["accounts"][0]["email"], "qa-tester@gmail.com")
            self.assertFalse(reg_body["accounts"][0]["has_logged_in"])

            # Snapshot persisted to storage & hydrates cleanly into a fresh DB
            fresh_store = ProjectStore(root / "fresh.db")
            self.assertTrue(hydrate_internal_accounts_from_storage(fresh_store, storage))
            self.assertTrue(fresh_store.is_internal_email("qa-tester@gmail.com"))

            # Log in as the internal tester (0 credits in wallet)
            login = client.post("/v1/auth/google", json={"credential": "tok-qa-tester"})
            # FakeGoogleVerifier ignores token email formatting unless default; login manually with qa email via second client
            qa_client = TestClient(app)
            qa_user = AuthenticatedUser(user_id="usr_qa_1", email="qa-tester@gmail.com", name="QA Tester")
            store.upsert_user(qa_user)
            from app.auth import SESSION_COOKIE_NAME, issue_session_token

            tok, _ = issue_session_token(qa_user, settings.session_secret)
            qa_client.cookies.set(SESSION_COOKIE_NAME, tok)

            wallet = qa_client.get("/v1/billing/wallet")
            self.assertEqual(wallet.status_code, 200, wallet.text)
            self.assertEqual(wallet.json()["credits"], 0)
            self.assertTrue(wallet.json()["is_internal"])

            pid = self._create_project_with_upload(qa_client)

            # Even with 0 credits and daily_render_limit=1, internal account renders twice without 402/429
            r1 = qa_client.post(
                f"/v1/projects/{pid}/renders",
                json={"selected_type": "A", "skip_drafts": True, "dry_run": False},
            )
            self.assertEqual(r1.status_code, 202, r1.text)
            self.assertEqual(r1.json()["deducted_credits"], 0)
            self.assertEqual(r1.json()["quota"]["remaining_today"], 9999)

            r2 = qa_client.post(
                f"/v1/projects/{pid}/renders",
                json={"selected_type": "A", "skip_drafts": True, "dry_run": False},
            )
            self.assertEqual(r2.status_code, 202, r2.text)
            self.assertEqual(r2.json()["deducted_credits"], 0)

            # Now turn OFF internal status via Admin DELETE -> next render hits 402 insufficient credits
            off = client.delete(
                "/v1/admin/accounts/internal/qa-tester@gmail.com",
                headers=admin_hdr,
            )
            self.assertEqual(off.status_code, 200, off.text)
            self.assertEqual(off.json()["internal_count"], 0)

            wallet_after = qa_client.get("/v1/billing/wallet")
            self.assertFalse(wallet_after.json()["is_internal"])

            r3 = qa_client.post(
                f"/v1/projects/{pid}/renders",
                json={"selected_type": "A", "skip_drafts": True, "dry_run": False},
            )
            self.assertEqual(r3.status_code, 429)  # daily quota limit=1 already exceeded for regular account
            _ = login

    def test_immediate_render_cancel_stops_running_job_and_refunds_once(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            app, settings, store, _storage = self._setup_app(root, daily_render_limit=5)
            client = TestClient(app)

            user = AuthenticatedUser(user_id="usr_norm_1", email="norm@gmail.com", name="Normal User")
            store.upsert_user(user)
            store.refund_wallet_credits(user.user_id, 24)
            from app.auth import SESSION_COOKIE_NAME, issue_session_token

            tok, _ = issue_session_token(user, settings.session_secret)
            client.cookies.set(SESSION_COOKIE_NAME, tok)

            # Create project and insert a worker-style scenario + upload so hookpipe path runs
            proj = store.create_project(
                "prj_cancel_test",
                user.user_id,
                product={
                    "name": "테스트 제품",
                    "category": "living",
                    "verified_facts": ["단단하고 가볍다"],
                },
                selected_types=["C"],
                flow_mode="guide_first",
            )
            scn_id = "scn_worker_c_01"
            store.save_scenarios(
                proj["project_id"],
                [
                    {
                        "scenario_id": scn_id,
                        "type": "C",
                        "hook_title": "테스트 훅",
                        "beats": [
                            {
                                "order": 1,
                                "role": "문제",
                                "duration_sec": 5.0,
                                "visual": "화면",
                                "narration": "짧은 테스트 문장입니다.",
                                "caption": "짧은 자막",
                            }
                        ],
                        "ad_spec": {"track_archetype": "C_direct_proof"},
                    }
                ],
            )
            store.update_project(proj["project_id"], selected_scenario_id=scn_id)
            fake_clip = root / "upload_01.mp4"
            fake_clip.write_bytes(b"fake-video-bytes")
            store.update_project(
                proj["project_id"],
                uploads={
                    "clips": [{"shot_no": 1, "local_path": str(fake_clip), "duration_sec": 10.0}],
                    "total_duration_sec": 10.0,
                },
            )

            # Simulate an active running job directly via HookPipeline cancel_job + API cancel endpoint
            started = threading.Event()
            release = threading.Event()

            from hookpipe.render import _call_with_deadline, JobCancelledError

            cancel_ev = app.state.project_store  # keep reference
            _ = cancel_ev

            # Test cooperative _call_with_deadline cancellation speed (< 1.5s even with 60s task)
            from hookpipe.service import HookPipeline
            from app.store import JobStore

            job_store = app.state.store
            hp = HookPipeline(settings, store, job_store, _storage)
            jid = "job_live_cancel_1"
            store.refund_wallet_credits(user.user_id, 0)
            self.assertTrue(store.deduct_wallet_credits(user.user_id, 12))
            job_store.create_job(
                jid,
                proj["project_id"],
                {"pipeline": "hookpipe"},
                status="RUNNING",
                stage="HOOK:CLIP 1/2",
                deducted_credits=12,
                refunded_credits=0,
            )
            store.update_project(proj["project_id"], status="RENDERING", latest_job_id=jid)

            ev = hp._begin_job_cancel_scope(jid)
            errors: list[BaseException] = []

            def worker() -> None:
                started.set()
                try:
                    _call_with_deadline(
                        lambda: release.wait(60.0),
                        60.0,
                        "느린 영상 생성",
                        cancel_event=ev,
                    )
                except BaseException as exc:
                    errors.append(exc)

            t = threading.Thread(target=worker, daemon=True)
            t.start()
            self.assertTrue(started.wait(2.0))

            # Call cancel endpoint; verify immediate return, CANCELED status, and exact credit refund
            t0 = time.monotonic()
            resp = client.post(
                f"/v1/projects/{proj['project_id']}/renders/cancel",
                json={"job_id": jid},
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            body = resp.json()
            self.assertEqual(body["status"], "CANCELED")
            self.assertTrue(body["canceled"])
            self.assertEqual(body["refunded_credits"], 12)
            self.assertEqual(body["credits"], 24)

            # Second cancel call must NOT double-refund
            resp2 = client.post(
                f"/v1/projects/{proj['project_id']}/renders/cancel",
                json={"job_id": jid},
            )
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["refunded_credits"], 0)
            self.assertEqual(resp2.json()["credits"], 24)

            # Project status restored from RENDERING to UPLOADS_READY
            proj_after = store.get_project(proj["project_id"])
            self.assertEqual(proj_after["status"], "UPLOADS_READY")

            # Also verify _call_with_deadline unblocks immediately when cancel_job is called
            hp.cancel_job(jid)
            t.join(timeout=2.0)
            self.assertLess(time.monotonic() - t0, 2.5)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], JobCancelledError)
            release.set()


if __name__ == "__main__":
    unittest.main()
