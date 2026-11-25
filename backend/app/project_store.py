"""SQLite WAL persistence for users, NAPDA projects, scenarios, and daily render quotas."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .auth import AuthenticatedUser


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today_utc_str(now: Optional[datetime] = None) -> str:
    return (now or _now_utc()).strftime("%Y-%m-%d")


class ProjectStore:
    """Thread-safe SQLite WAL store backing `/v1/auth/*` and `/v1/projects/*`."""

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
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT,
                    picture TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    flow_mode TEXT NOT NULL,
                    product_json TEXT NOT NULL,
                    selected_types_json TEXT NOT NULL,
                    selected_scenario_id TEXT,
                    filming_guide_json TEXT,
                    uploads_json TEXT,
                    latest_job_id TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_user_updated
                    ON projects(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    hook_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    storyboard_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scenarios_project
                    ON scenarios(project_id, created_at ASC);

                CREATE TABLE IF NOT EXISTS render_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_render_usage_user_day
                    ON render_usage(user_id, day_utc);
                """
            )

    def upsert_user(self, user: AuthenticatedUser) -> Dict[str, Any]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, email, name, picture, created_at, last_login_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    email = excluded.email,
                    name = excluded.name,
                    picture = excluded.picture,
                    last_login_at = excluded.last_login_at
                """,
                (user.user_id, user.email, user.name, user.picture, now_iso, now_iso),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user.user_id,)).fetchone()
        return dict(row)  # type: ignore[arg-type]

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "project_id": row["id"],
            "user_id": row["user_id"],
            "status": row["status"],
            "flow_mode": row["flow_mode"],
            "product": json.loads(row["product_json"]),
            "selected_types": json.loads(row["selected_types_json"]),
            "selected_scenario_id": row["selected_scenario_id"],
            "filming_guide": json.loads(row["filming_guide_json"]) if row["filming_guide_json"] else None,
            "uploads": json.loads(row["uploads_json"]) if row["uploads_json"] else None,
            "latest_job_id": row["latest_job_id"],
            "expires_at": row["expires_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_project(
        self,
        project_id: str,
        user_id: str,
        *,
        product: Dict[str, Any],
        selected_types: List[str],
        flow_mode: str,
        retention_ttl_days: int = 7,
    ) -> Dict[str, Any]:
        now = _now_utc()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(days=max(1, int(retention_ttl_days)))).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    id, user_id, status, flow_mode, product_json, selected_types_json,
                    expires_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    user_id,
                    "PRODUCT_SAVED",
                    flow_mode,
                    json.dumps(product, ensure_ascii=False),
                    json.dumps(selected_types, ensure_ascii=False),
                    expires_iso,
                    now_iso,
                    now_iso,
                ),
            )
        return self.get_project(project_id, user_id=user_id)  # type: ignore[return-value]

    def get_project(
        self, project_id: str, *, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            if user_id is None:
                row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                    (project_id, user_id),
                ).fetchone()
        return self._row_to_project(row) if row else None

    def list_projects_for_user(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, int(limit)),
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def update_project(
        self,
        project_id: str,
        *,
        status: Optional[str] = None,
        selected_scenario_id: Optional[str] = None,
        filming_guide: Optional[Dict[str, Any]] = None,
        uploads: Optional[Dict[str, Any]] = None,
        latest_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        fields = ["updated_at = ?"]
        vals: List[Any] = [_now_utc().isoformat()]
        if status is not None:
            fields.append("status = ?")
            vals.append(status)
        if selected_scenario_id is not None:
            fields.append("selected_scenario_id = ?")
            vals.append(selected_scenario_id)
        if filming_guide is not None:
            fields.append("filming_guide_json = ?")
            vals.append(json.dumps(filming_guide, ensure_ascii=False))
        if uploads is not None:
            fields.append("uploads_json = ?")
            vals.append(json.dumps(uploads, ensure_ascii=False))
        if latest_job_id is not None:
            fields.append("latest_job_id = ?")
            vals.append(latest_job_id)
        vals.append(project_id)

        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", vals)
        return self.get_project(project_id)  # type: ignore[return-value]

    def save_scenarios(self, project_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM scenarios WHERE project_id = ?", (project_id,))
            for it in items:
                conn.execute(
                    """
                    INSERT INTO scenarios (scenario_id, project_id, hook_type, payload_json, storyboard_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        it["scenario_id"],
                        project_id,
                        it["type"],
                        json.dumps(it, ensure_ascii=False),
                        json.dumps(it.get("storyboard_frames") or [], ensure_ascii=False),
                        now_iso,
                    ),
                )
        return self.list_scenarios(project_id)

    @staticmethod
    def _row_to_scenario(row: sqlite3.Row) -> Dict[str, Any]:
        data = json.loads(row["payload_json"])
        if row["storyboard_json"]:
            data["storyboard_frames"] = json.loads(row["storyboard_json"])
        return data

    def list_scenarios(self, project_id: str) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scenarios WHERE project_id = ? ORDER BY created_at ASC",
                (project_id,),
            ).fetchall()
        return [self._row_to_scenario(r) for r in rows]

    def get_scenario(self, project_id: str, scenario_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scenarios WHERE project_id = ? AND scenario_id = ?",
                (project_id, scenario_id),
            ).fetchone()
        return self._row_to_scenario(row) if row else None

    def update_scenario_storyboard(
        self, project_id: str, scenario_id: str, frames: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE scenarios SET storyboard_json = ? WHERE project_id = ? AND scenario_id = ?",
                (json.dumps(frames, ensure_ascii=False), project_id, scenario_id),
            )
        return self.get_scenario(project_id, scenario_id)

    def count_user_renders_today(self, user_id: str, *, now: Optional[datetime] = None) -> int:
        day = _today_utc_str(now)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM render_usage WHERE user_id = ? AND day_utc = ?",
                (user_id, day),
            ).fetchone()
        return int(row["cnt"] if row else 0)

    def record_render_usage(
        self, user_id: str, project_id: str, job_id: str, *, now: Optional[datetime] = None
    ) -> None:
        cur = now or _now_utc()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO render_usage (user_id, project_id, job_id, day_utc, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, project_id, job_id, _today_utc_str(cur), cur.isoformat()),
            )
