"""Tests for R2 SQLite backup and startup hydration across Cloud Run container restarts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db_persistence import SQLITE_STATE_OBJECT_KEY, SqliteStorageSyncer, hydrate_sqlite_from_storage  # noqa: E402
from app.project_store import ProjectStore  # noqa: E402
from app.storage import LocalStorageBackend  # noqa: E402
from app.store import JobStore  # noqa: E402
from tests.support.tempdirs import temporary_directory  # noqa: E402


class FakeR2Storage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_file(self, local_path: str | Path, object_key: str) -> str:
        self.objects[object_key] = Path(local_path).read_bytes()
        return f"https://r2.example/{object_key}"

    def download_file(self, object_key: str, local_path: str | Path) -> str:
        if object_key not in self.objects:
            raise FileNotFoundError(object_key)
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.objects[object_key])
        return str(dest)

    def head_object(self, object_key: str) -> dict | None:
        return {"size": len(self.objects[object_key])} if object_key in self.objects else None


class TestSqliteR2Persistence(unittest.TestCase):
    def test_flush_and_hydrate_preserves_projects_jobs_and_usage_summary(self) -> None:
        remote = FakeR2Storage()
        with temporary_directory() as td1, temporary_directory() as td2:
            db1 = Path(td1) / "jobs.db"
            proj1 = ProjectStore(db1)
            job1 = JobStore(db1)

            syncer = SqliteStorageSyncer(db1, remote)
            self.assertTrue(syncer.enabled)
            proj1.set_on_write(syncer.schedule_sync)
            job1.set_on_write(syncer.schedule_sync)

            proj1.create_project(
                "prj_persist_01",
                "usr_01",
                product={"name": "포터블 타이머", "category": "living", "verified_facts": ["저소음"]},
                selected_types=["A"],
                flow_mode="guide_first",
            )
            job1.create_job("job_persist_01", "prj_persist_01", {"type": "A"}, status="QC_READY", stage="QC_READY")
            proj1.record_api_usage(
                project_id="prj_persist_01",
                user_id="usr_01",
                job_id="job_persist_01",
                hook_type="A",
                stage="video_clip",
                provider="google",
                model="gemini-omni-flash-preview",
                media_unit="sec",
                media_qty=10.0,
                estimated_cost_usd=1.0,
            )

            expected_summary = proj1.get_usage_summary(days=30, limit_projects=20)
            self.assertTrue(syncer.flush())
            self.assertIn(SQLITE_STATE_OBJECT_KEY, remote.objects)

            # Simulate fresh Cloud Run container with empty local disk
            db2 = Path(td2) / "fresh" / "jobs.db"
            self.assertTrue(hydrate_sqlite_from_storage(db2, remote))
            proj2 = ProjectStore(db2)
            job2 = JobStore(db2)

            restored_proj = proj2.get_project("prj_persist_01")
            self.assertIsNotNone(restored_proj)
            assert restored_proj is not None
            self.assertEqual(restored_proj["product"]["name"], "포터블 타이머")

            restored_job = job2.get_job("job_persist_01")
            self.assertIsNotNone(restored_job)
            assert restored_job is not None
            self.assertEqual(restored_job["status"], "QC_READY")

            restored_summary = proj2.get_usage_summary(days=30, limit_projects=20)
            self.assertEqual(restored_summary["totals"]["total_calls"], expected_summary["totals"]["total_calls"])
            self.assertAlmostEqual(
                restored_summary["totals"]["estimated_cost_usd"],
                expected_summary["totals"]["estimated_cost_usd"],
                places=6,
            )

    def test_corrupt_remote_snapshot_is_rejected_without_crashing(self) -> None:
        remote = FakeR2Storage()
        remote.objects[SQLITE_STATE_OBJECT_KEY] = b"not-a-valid-sqlite-database"
        with temporary_directory() as td:
            db_path = Path(td) / "jobs.db"
            self.assertFalse(hydrate_sqlite_from_storage(db_path, remote))
            self.assertFalse(db_path.exists())

    def test_local_storage_backend_is_noop(self) -> None:
        with temporary_directory() as td:
            local_storage = LocalStorageBackend(Path(td) / "objects")
            db_path = Path(td) / "jobs.db"
            syncer = SqliteStorageSyncer(db_path, local_storage)
            self.assertFalse(syncer.enabled)
            self.assertFalse(syncer.flush())
            self.assertFalse(hydrate_sqlite_from_storage(db_path, local_storage))
