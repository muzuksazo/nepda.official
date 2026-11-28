"""SQLite WAL state store for pipeline jobs and past Track-A campaign archetypes."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Thread-safe SQLite WAL persistence for jobs and cross-campaign reskin history."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        on_write: Optional[Callable[[], None]] = None,
    ) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._on_write: Optional[Callable[[], None]] = on_write
        self._init_schema()

    def set_on_write(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_write = callback

    def _notify_write(self) -> None:
        cb = self._on_write
        if cb is not None:
            try:
                cb()
            except Exception:
                pass

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
                    deducted_credits INTEGER NOT NULL DEFAULT 0,
                    refunded_credits INTEGER NOT NULL DEFAULT 0,
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
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "deducted_credits" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN deducted_credits INTEGER NOT NULL DEFAULT 0")
            if "refunded_credits" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN refunded_credits INTEGER NOT NULL DEFAULT 0")

    def create_job(
        self,
        job_id: str,
        campaign_id: str,
        payload: Dict[str, Any],
        *,
        status: str = "QUEUED",
        stage: str = "QUEUED",
        deducted_credits: int = 0,
        refunded_credits: int = 0,
    ) -> Dict[str, Any]:
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, campaign_id, status, stage, payload_json,
                    deducted_credits, refunded_credits, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    campaign_id,
                    status,
                    stage,
                    json.dumps(payload, ensure_ascii=False),
                    max(0, int(deducted_credits)),
                    max(0, int(refunded_credits)),
                    now,
                    now,
                ),
            )
        self._notify_write()
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
        deducted_credits: Optional[int] = None,
        refunded_credits: Optional[int] = None,
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
        if deducted_credits is not None:
            fields.append("deducted_credits = ?")
            vals.append(max(0, int(deducted_credits)))
        if refunded_credits is not None:
            fields.append("refunded_credits = ?")
            vals.append(max(0, int(refunded_credits)))
        vals.append(job_id)

        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", vals)
        self._notify_write()
        return self.get_job(job_id)  # type: ignore[return-value]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        def _loads(val: Optional[str]) -> Any:
            return json.loads(val) if val else None

        keys = set(row.keys())
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
            "deducted_credits": int(row["deducted_credits"] or 0) if "deducted_credits" in keys else 0,
            "refunded_credits": int(row["refunded_credits"] or 0) if "refunded_credits" in keys else 0,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (int(limit), max(0, int(offset))),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_jobs_by_status(self, statuses: List[str] | tuple[str, ...]) -> List[Dict[str, Any]]:
        if not statuses:
            return []
        placeholders = ", ".join("?" for _ in statuses)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY created_at ASC",
                tuple(statuses),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_jobs(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM jobs").fetchone()
        return int(row["cnt"] if row else 0)

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
