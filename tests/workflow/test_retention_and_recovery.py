"""FR-008 & FR-014 · Orphan job recovery, live status sync & 7-day TTL expiration cleanup tests."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.retention import prune_expired_data, recover_orphaned_jobs  # noqa: E402
from app.server import create_app  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from app.store import JobStore  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tests.support.projects_api import fake_google_verifier, login_client  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class TestRetentionAndRecovery(unittest.TestCase):
    def test_startup_recovers_orphaned_jobs_and_hooks(self) -> None:
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

            proj = proj_store.create_project(
                "prj_orphan1",
                "user-1",
                product={"name": "스펀지", "category": "living", "verified_facts": ["흡수"]},
                selected_types=["A"],
                flow_mode="guide_first",
            )
            job_store.create_job("job_stuck", proj["project_id"], {}, status="RUNNING", stage="GENERATING")
            proj_store.update_project(proj["project_id"], status="RENDERING", latest_job_id="job_stuck")

            proj_hk = proj_store.create_project(
                "prj_orphan2",
                "user-1",
                product={"name": "타이머", "category": "stationery", "verified_facts": ["60분"]},
                selected_types=["C"],
                flow_mode="guide_first",
            )
            proj_store.create_hook(
                hook_id="hook_stuck",
                project_id=proj_hk["project_id"],
                user_id="user-1",
                scenario_id="scn_1",
                job_id="job_hk",
                tts={"enabled": True},
                output_dir=str(root / "outputs" / "hook_stuck"),
                status="running",
            )
            proj_store.update_project(proj_hk["project_id"], status="HOOK_RENDERING")

            # Creating FastAPI app triggers lifespan recovery on startup
            app = create_app(
                settings=settings,
                store=job_store,
                project_store=proj_store,
                google_token_verifier=fake_google_verifier,
            )
            with TestClient(app):
                pass

            self.assertEqual(job_store.get_job("job_stuck")["status"], "FAILED")
            self.assertEqual(proj_store.get_project("prj_orphan1")["status"], "FAILED")
            self.assertEqual(proj_store.get_hook("prj_orphan2", "hook_stuck")["status"], "failed")
            self.assertEqual(proj_store.get_project("prj_orphan2")["status"], "STORYBOARD_READY")

            # Also test recover_orphaned_jobs directly
            summary = recover_orphaned_jobs(job_store, proj_store)
            self.assertEqual(summary["recovered_jobs"], 0)

    def test_expired_project_blocked_with_410_and_pruned(self) -> None:
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
            login_client(client, "seller-exp:exp@example.com")

            pid = client.post(
                "/v1/projects",
                json={
                    "product": {"name": "만료 제품", "category": "living", "verified_facts": ["테스트"]},
                    "selected_types": ["A"],
                },
            ).json()["project_id"]

            # Put a file into storage and project work_dir
            dummy_file = root / "dummy.mp4"
            dummy_file.write_bytes(b"video-bytes")
            storage.upload_file(dummy_file, f"uploads/seller-exp/{pid}/shot_01.mp4")
            proj_store.update_project(
                pid,
                uploads={"clips": [{"shot_no": 1, "object_key": f"uploads/seller-exp/{pid}/shot_01.mp4"}]},
            )
            (Path(settings.work_root) / pid).mkdir(parents=True, exist_ok=True)
            (Path(settings.work_root) / pid / "temp.txt").write_text("x", encoding="utf-8")

            # Force expires_at into the past
            past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            with proj_store._connect() as conn:  # noqa: SLF001
                conn.execute("UPDATE projects SET expires_at = ? WHERE id = ?", (past_iso, pid))

            resp = client.get(f"/v1/projects/{pid}")
            self.assertEqual(resp.status_code, 410)
            self.assertEqual(resp.json()["detail"]["error"]["code"], "PROJECT_EXPIRED")

            # Prune expired data
            prune_res = prune_expired_data(proj_store, job_store, storage, settings)
            self.assertEqual(prune_res["expired_projects"], 1)
            self.assertGreaterEqual(prune_res["deleted_objects"], 1)
            self.assertIsNone(proj_store.get_project(pid))
            self.assertIsNone(storage.resolve_local_path(f"uploads/seller-exp/{pid}/shot_01.mp4"))
            self.assertFalse((Path(settings.work_root) / pid).exists())
