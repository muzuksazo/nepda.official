"""SQLite WAL state store for pipeline jobs and past Track-A campaign archetypes."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Thread-safe SQLite WAL persistence for jobs and cross-campaign reskin history."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    lint_json TEXT,
                    generation_json TEXT,
                    artifacts_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

                CREATE TABLE IF NOT EXISTS past_campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    a_genre_archetype TEXT,
                    spec_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_job(
        self,
        job_id: str,
        campaign_id: str,
        payload: Dict[str, Any],
        *,
        status: str = "QUEUED",
        stage: str = "QUEUED",
    ) -> Dict[str, Any]:
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, campaign_id, status, stage, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, campaign_id, status, stage, json.dumps(payload, ensure_ascii=False), now, now),
            )
        return self.get_job(job_id)  # type: ignore[return-value]

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        lint: Optional[Dict[str, Any]] = None,
        generation: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        fields: List[str] = ["updated_at = ?"]
        vals: List[Any] = [_now_iso()]
        if status is not None:
            fields.append("status = ?")
            vals.append(status)
        if stage is not None:
            fields.append("stage = ?")
            vals.append(stage)
        if lint is not None:
            fields.append("lint_json = ?")
            vals.append(json.dumps(lint, ensure_ascii=False))
        if generation is not None:
            fields.append("generation_json = ?")
            vals.append(json.dumps(generation, ensure_ascii=False))
        if artifacts is not None:
            fields.append("artifacts_json = ?")
            vals.append(json.dumps(artifacts, ensure_ascii=False))
        if error is not None:
            fields.append("error = ?")
            vals.append(error)
        vals.append(job_id)

        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", vals)
        return self.get_job(job_id)  # type: ignore[return-value]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        def _loads(val: Optional[str]) -> Any:
            return json.loads(val) if val else None

        return {
            "id": row["id"],
            "campaign_id": row["campaign_id"],
            "status": row["status"],
            "stage": row["stage"],
            "payload": _loads(row["payload_json"]) or {},
            "lint": _loads(row["lint_json"]),
            "generation": _loads(row["generation_json"]),
            "artifacts": _loads(row["artifacts_json"]),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def register_past_campaign(
        self,
        campaign_id: str,
        a_genre_archetype: Optional[str],
        spec_path: str | Path,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO past_campaigns (campaign_id, a_genre_archetype, spec_path, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(campaign_id) DO UPDATE SET
                    a_genre_archetype = excluded.a_genre_archetype,
                    spec_path = excluded.spec_path
                """,
                (campaign_id, a_genre_archetype, str(Path(spec_path).resolve()), _now_iso()),
            )

    def list_past_campaigns(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT campaign_id, a_genre_archetype, spec_path, created_at FROM past_campaigns ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
