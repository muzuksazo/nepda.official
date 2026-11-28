"""내 영상 지우기: DELETE /v1/projects/{id} (2026-11-29)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth import AuthenticatedUser, SESSION_COOKIE_NAME, issue_session_token  # noqa: E402
from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from tests.support.projects_api import fake_google_verifier, fake_scenario_generator  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestProjectDelete(unittest.TestCase):
    def _setup(self, root: Path):
        settings = Settings(
            _env_file=None,
            gemini_api_key="dummy-key",
            google_client_id="client-id",
            session_secret="test-session-secret-0123456789abcdef",
            hook_render_mode="dry_run",
            credits_per_video=12,
            initial_free_videos=0,
            work_root=str(root / "work"),
            output_dir=str(root / "outputs"),
            db_path=str(root / "napda.db"),
        )
        store = ProjectStore(settings.db_path)
        storage = LocalStorageBackend(root / "storage")
        app = create_app(
            settings,
            project_store=store,
            storage=storage,
            google_token_verifier=fake_google_verifier,
            scenario_generator=fake_scenario_generator,
        )
        return app, settings, store, storage

    def _client_for(self, app, settings, store, user_id: str) -> TestClient:
        user = AuthenticatedUser(user_id=user_id, email=f"{user_id}@gmail.com", name=user_id)
        store.upsert_user(user)
        client = TestClient(app)
        tok, _ = issue_session_token(user, settings.session_secret)
        client.cookies.set(SESSION_COOKIE_NAME, tok)
        return client

    def test_owner_deletes_finished_project_and_its_files(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            app, settings, store, storage = self._setup(root)
            client = self._client_for(app, settings, store, "usr_owner")
            proj = store.create_project(
                "prj_del_done", "usr_owner", product={"name": "스펀지", "verified_facts": ["가볍다"]},
                selected_types=["B"], flow_mode="guide_first",
            )
            key = "uploads/usr_owner/prj_del_done/shot_01.mp4"
            (root / "storage" / key).parent.mkdir(parents=True, exist_ok=True)
            (root / "storage" / key).write_bytes(b"clip")
            store.update_project(proj["project_id"], uploads={"clips": [{"shot_no": 1, "object_key": key}]})
            work = root / "work" / proj["project_id"]
            work.mkdir(parents=True)
            (work / "a.txt").write_text("x", encoding="utf-8")

            other = self._client_for(app, settings, store, "usr_other")
            self.assertEqual(other.delete(f"/v1/projects/{proj['project_id']}").status_code, 404)  # 남의 영상은 못 지운다

            resp = client.delete(f"/v1/projects/{proj['project_id']}")
            self.assertEqual(resp.status_code, 204, resp.text)
            self.assertIsNone(store.get_project(proj["project_id"]))
            self.assertFalse((root / "storage" / key).exists())
            self.assertFalse(work.exists())
            self.assertEqual(client.delete(f"/v1/projects/{proj['project_id']}").status_code, 404)

    def test_deleting_a_running_project_cancels_and_refunds_first(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            app, settings, store, _storage = self._setup(root)
            client = self._client_for(app, settings, store, "usr_run")
            store.refund_wallet_credits("usr_run", 12)
            self.assertTrue(store.deduct_wallet_credits("usr_run", 12))
            proj = store.create_project(
                "prj_del_run", "usr_run", product={"name": "타이머", "verified_facts": ["60분형"]},
                selected_types=["C"], flow_mode="guide_first",
            )
            job_store = app.state.store
            job_store.create_job(
                "job_del_run", proj["project_id"], {"pipeline": "hookpipe"}, status="RUNNING",
                stage="HOOK:CLIP 1/2", deducted_credits=12, refunded_credits=0,
            )
            store.update_project(proj["project_id"], status="RENDERING", latest_job_id="job_del_run")

            resp = client.delete(f"/v1/projects/{proj['project_id']}")
            self.assertEqual(resp.status_code, 204, resp.text)
            self.assertIsNone(store.get_project(proj["project_id"]))
            self.assertEqual(job_store.get_job("job_del_run")["status"], "CANCELED")
            wallet = store.get_or_create_wallet("usr_run", default_free_videos=0)
            self.assertEqual(wallet["credits"], 12)


if __name__ == "__main__":
    unittest.main()
