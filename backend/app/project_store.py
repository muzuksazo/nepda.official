"""SQLite WAL persistence for users, NAPDA projects, scenarios, and daily render quotas."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
                    scenario_round INTEGER NOT NULL DEFAULT 0,
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

                CREATE TABLE IF NOT EXISTS product_info_cache (
                    product_info_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    normalized_hash TEXT NOT NULL,
                    product_json TEXT NOT NULL,
                    source_url TEXT,
                    cached_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_product_info_user_hash
                    ON product_info_cache(user_id, normalized_hash);

                CREATE TABLE IF NOT EXISTS hooks (
                    hook_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tts_json TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_hooks_project_created
                    ON hooks(project_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS credit_wallets (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    free_videos_remaining INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS billing_orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    package_id TEXT NOT NULL,
                    credits INTEGER NOT NULL,
                    amount_krw INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'KRW',
                    paddle_price_id TEXT NOT NULL,
                    paddle_transaction_id TEXT UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_billing_orders_user_created
                    ON billing_orders(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS credit_ledger (
                    entry_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(reason, reference_id)
                );
                CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created
                    ON credit_ledger(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS paddle_webhook_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    transaction_id TEXT,
                    payload_json TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                );
                """
            )
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(projects)").fetchall()}
            if "scenario_round" not in cols:
                conn.execute("ALTER TABLE projects ADD COLUMN scenario_round INTEGER NOT NULL DEFAULT 0")
            if "body_json" not in cols:
                conn.execute("ALTER TABLE projects ADD COLUMN body_json TEXT")
            if "thumbnail_json" not in cols:
                conn.execute("ALTER TABLE projects ADD COLUMN thumbnail_json TEXT")

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
        keys = set(row.keys())
        return {
            "project_id": row["id"],
            "user_id": row["user_id"],
            "status": row["status"],
            "flow_mode": row["flow_mode"],
            "product": json.loads(row["product_json"]),
            "selected_types": json.loads(row["selected_types_json"]),
            "selected_scenario_id": row["selected_scenario_id"],
            "scenario_round": int(row["scenario_round"] or 0) if "scenario_round" in keys else 0,
            "filming_guide": json.loads(row["filming_guide_json"]) if row["filming_guide_json"] else None,
            "uploads": json.loads(row["uploads_json"]) if row["uploads_json"] else None,
            "body": json.loads(row["body_json"]) if ("body_json" in keys and row["body_json"]) else None,
            "thumbnail": json.loads(row["thumbnail_json"]) if ("thumbnail_json" in keys and row["thumbnail_json"]) else None,
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

    def list_projects_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                (user_id, int(limit), max(0, int(offset))),
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def count_projects_for_user(self, user_id: str) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM projects WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["cnt"] if row else 0)

    def update_project(
        self,
        project_id: str,
        *,
        status: Optional[str] = None,
        selected_scenario_id: Optional[str] = None,
        filming_guide: Optional[Dict[str, Any]] = None,
        uploads: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        thumbnail: Optional[Dict[str, Any]] = None,
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
        if body is not None:
            fields.append("body_json = ?")
            vals.append(json.dumps(body, ensure_ascii=False))
        if thumbnail is not None:
            fields.append("thumbnail_json = ?")
            vals.append(json.dumps(thumbnail, ensure_ascii=False))
        if latest_job_id is not None:
            fields.append("latest_job_id = ?")
            vals.append(latest_job_id)
        vals.append(project_id)

        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", vals)
        return self.get_project(project_id)  # type: ignore[return-value]

    def list_projects_by_status(self, statuses: List[str] | Tuple[str, ...]) -> List[Dict[str, Any]]:
        if not statuses:
            return []
        placeholders = ", ".join("?" for _ in statuses)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM projects WHERE status IN ({placeholders}) ORDER BY updated_at ASC",
                tuple(statuses),
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def list_expired_projects(self, now_iso: Optional[str] = None) -> List[Dict[str, Any]]:
        cutoff = now_iso or _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE expires_at <= ? ORDER BY expires_at ASC",
                (cutoff,),
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def delete_project_cascade(self, project_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM hooks WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM scenarios WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM render_usage WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def delete_expired_product_info_cache(self, now_iso: Optional[str] = None) -> int:
        cutoff = now_iso or _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM product_info_cache WHERE expires_at <= ?",
                (cutoff,),
            )
            return int(cur.rowcount or 0)

    def list_hooks_by_status(self, statuses: List[str] | Tuple[str, ...]) -> List[Dict[str, Any]]:
        if not statuses:
            return []
        placeholders = ", ".join("?" for _ in statuses)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM hooks WHERE status IN ({placeholders}) ORDER BY created_at ASC",
                tuple(statuses),
            ).fetchall()
        return [self._row_to_hook(r) for r in rows]

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

    def append_scenarios(self, project_id: str, items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
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
            conn.execute(
                "UPDATE projects SET scenario_round = COALESCE(scenario_round, 0) + 1, updated_at = ? WHERE id = ?",
                (now_iso, project_id),
            )
            row = conn.execute("SELECT scenario_round FROM projects WHERE id = ?", (project_id,)).fetchone()
            new_round = int(row["scenario_round"] or 1) if row else 1
        return self.list_scenarios(project_id), new_round

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

    def upsert_product_info_cache(
        self,
        user_id: str,
        *,
        product: Dict[str, Any],
        source_url: Optional[str] = None,
        ttl_sec: int = 3600,
    ) -> Dict[str, Any]:
        canonical = json.dumps(
            {"product": product, "source_url": source_url or None},
            ensure_ascii=False,
            sort_keys=True,
        )
        norm_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        now = _now_utc()
        now_iso = now.isoformat()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM product_info_cache
                WHERE user_id = ? AND normalized_hash = ? AND expires_at > ?
                ORDER BY cached_at DESC LIMIT 1
                """,
                (user_id, norm_hash, now_iso),
            ).fetchone()
            if existing:
                return {
                    "product_info_id": existing["product_info_id"],
                    "product": json.loads(existing["product_json"]),
                    "source_url": existing["source_url"],
                    "cached": True,
                    "cached_at": existing["cached_at"],
                    "expires_at": existing["expires_at"],
                }

            pid = f"pi_{uuid.uuid4().hex[:12]}"
            expires_iso = (now + timedelta(seconds=max(1, int(ttl_sec)))).isoformat()
            conn.execute(
                """
                INSERT INTO product_info_cache (
                    product_info_id, user_id, normalized_hash, product_json, source_url, cached_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, user_id, norm_hash, json.dumps(product, ensure_ascii=False), source_url, now_iso, expires_iso),
            )
        return {
            "product_info_id": pid,
            "product": product,
            "source_url": source_url,
            "cached": False,
            "cached_at": now_iso,
            "expires_at": expires_iso,
        }

    def get_product_info(self, user_id: str, product_info_id: str) -> Optional[Dict[str, Any]]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM product_info_cache
                WHERE product_info_id = ? AND user_id = ? AND expires_at > ?
                """,
                (product_info_id, user_id, now_iso),
            ).fetchone()
        if not row:
            return None
        return {
            "product_info_id": row["product_info_id"],
            "product": json.loads(row["product_json"]),
            "source_url": row["source_url"],
            "cached_at": row["cached_at"],
            "expires_at": row["expires_at"],
        }

    @staticmethod
    def _row_to_hook(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "hook_id": row["hook_id"],
            "project_id": row["project_id"],
            "user_id": row["user_id"],
            "scenario_id": row["scenario_id"],
            "job_id": row["job_id"],
            "status": row["status"],
            "tts": json.loads(row["tts_json"]),
            "output_dir": row["output_dir"],
            "files": json.loads(row["files_json"]),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_hook(
        self,
        *,
        hook_id: str,
        project_id: str,
        user_id: str,
        scenario_id: str,
        job_id: str,
        tts: Dict[str, Any],
        output_dir: str,
        files: Optional[Dict[str, Any]] = None,
        status: str = "queued",
    ) -> Dict[str, Any]:
        now_iso = _now_utc().isoformat()
        default_files = files or {
            "hook_video": None,
            "tts_audio": None,
            "subtitles_srt": None,
            "scenario_json": None,
            "storyboard_images": [],
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hooks (
                    hook_id, project_id, user_id, scenario_id, job_id, status,
                    tts_json, output_dir, files_json, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    hook_id,
                    project_id,
                    user_id,
                    scenario_id,
                    job_id,
                    status,
                    json.dumps(tts, ensure_ascii=False),
                    output_dir,
                    json.dumps(default_files, ensure_ascii=False),
                    now_iso,
                    now_iso,
                ),
            )
        return self.get_hook(project_id, hook_id)  # type: ignore[return-value]

    def update_hook(
        self,
        hook_id: str,
        *,
        status: Optional[str] = None,
        files: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        fields = ["updated_at = ?"]
        vals: List[Any] = [_now_utc().isoformat()]
        if status is not None:
            fields.append("status = ?")
            vals.append(status)
        if files is not None:
            fields.append("files_json = ?")
            vals.append(json.dumps(files, ensure_ascii=False))
        if error is not None:
            fields.append("error = ?")
            vals.append(error)
        vals.append(hook_id)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE hooks SET {', '.join(fields)} WHERE hook_id = ?", vals)

    def get_hook(self, project_id: str, hook_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM hooks WHERE project_id = ? AND hook_id = ?",
                (project_id, hook_id),
            ).fetchone()
        return self._row_to_hook(row) if row else None

    def list_hooks_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM hooks WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._row_to_hook(r) for r in rows]

    @staticmethod
    def _row_to_wallet(row: sqlite3.Row) -> Dict[str, Any]:
        free_rem = int(row["free_videos_remaining"])
        return {
            "user_id": row["user_id"],
            "credits": int(row["balance"]),
            "free_videos_remaining": free_rem,
            "has_free_video": free_rem > 0,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_or_create_wallet(
        self, user_id: str, *, default_free_videos: int = 1
    ) -> Dict[str, Any]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO credit_wallets (
                    user_id, balance, free_videos_remaining, created_at, updated_at
                )
                VALUES (?, 0, ?, ?, ?)
                """,
                (user_id, max(0, int(default_free_videos)), now_iso, now_iso),
            )
            row = conn.execute(
                "SELECT * FROM credit_wallets WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_wallet(row)  # type: ignore[arg-type]

    @staticmethod
    def _row_to_billing_order(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "order_id": row["order_id"],
            "user_id": row["user_id"],
            "package_id": row["package_id"],
            "credits": int(row["credits"]),
            "amount_krw": int(row["amount_krw"]),
            "currency": row["currency"],
            "paddle_price_id": row["paddle_price_id"],
            "paddle_transaction_id": row["paddle_transaction_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
        }

    def create_billing_order(
        self,
        *,
        order_id: str,
        user_id: str,
        package_id: str,
        credits: int,
        amount_krw: int,
        currency: str,
        paddle_price_id: str,
        paddle_transaction_id: str,
    ) -> Dict[str, Any]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO billing_orders (
                    order_id, user_id, package_id, credits, amount_krw, currency,
                    paddle_price_id, paddle_transaction_id, status, created_at, updated_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, NULL)
                """,
                (
                    order_id,
                    user_id,
                    package_id,
                    int(credits),
                    int(amount_krw),
                    currency,
                    paddle_price_id,
                    paddle_transaction_id,
                    now_iso,
                    now_iso,
                ),
            )
            row = conn.execute(
                "SELECT * FROM billing_orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        return self._row_to_billing_order(row)  # type: ignore[arg-type]

    def get_billing_order(
        self, order_id: str, *, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            if user_id is None:
                row = conn.execute(
                    "SELECT * FROM billing_orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM billing_orders WHERE order_id = ? AND user_id = ?",
                    (order_id, user_id),
                ).fetchone()
        return self._row_to_billing_order(row) if row else None

    def get_billing_order_by_transaction(
        self, paddle_transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM billing_orders WHERE paddle_transaction_id = ?",
                (paddle_transaction_id,),
            ).fetchone()
        return self._row_to_billing_order(row) if row else None

    def complete_billing_order_atomic(
        self,
        *,
        order_id: Optional[str] = None,
        paddle_transaction_id: Optional[str] = None,
        event_id: Optional[str] = None,
        event_type: Optional[str] = None,
        payload_json: Optional[str] = None,
        default_free_videos: int = 1,
    ) -> Tuple[Optional[Dict[str, Any]], bool, Optional[Dict[str, Any]]]:
        """Atomically mark a pending billing order completed and credit the user's wallet once."""
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            if event_id:
                seen_evt = conn.execute(
                    "SELECT event_id FROM paddle_webhook_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if seen_evt:
                    order_row = None
                    if order_id:
                        order_row = conn.execute(
                            "SELECT * FROM billing_orders WHERE order_id = ?",
                            (order_id,),
                        ).fetchone()
                    if order_row is None and paddle_transaction_id:
                        order_row = conn.execute(
                            "SELECT * FROM billing_orders WHERE paddle_transaction_id = ?",
                            (paddle_transaction_id,),
                        ).fetchone()
                    if order_row is None:
                        return None, False, None
                    wallet_row = conn.execute(
                        "SELECT * FROM credit_wallets WHERE user_id = ?",
                        (order_row["user_id"],),
                    ).fetchone()
                    return (
                        self._row_to_billing_order(order_row),
                        False,
                        self._row_to_wallet(wallet_row) if wallet_row else None,
                    )

            order_row = None
            if order_id:
                order_row = conn.execute(
                    "SELECT * FROM billing_orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
            if order_row is None and paddle_transaction_id:
                order_row = conn.execute(
                    "SELECT * FROM billing_orders WHERE paddle_transaction_id = ?",
                    (paddle_transaction_id,),
                ).fetchone()
            if order_row is None:
                return None, False, None

            resolved_order_id = order_row["order_id"]
            uid = order_row["user_id"]
            conn.execute(
                """
                INSERT OR IGNORE INTO credit_wallets (
                    user_id, balance, free_videos_remaining, created_at, updated_at
                )
                VALUES (?, 0, ?, ?, ?)
                """,
                (uid, max(0, int(default_free_videos)), now_iso, now_iso),
            )

            existing_ledger = conn.execute(
                "SELECT entry_id FROM credit_ledger WHERE reason = 'paddle_charge' AND reference_id = ?",
                (resolved_order_id,),
            ).fetchone()

            credited = False
            if order_row["status"] != "completed" and existing_ledger is None:
                wallet_row = conn.execute(
                    "SELECT * FROM credit_wallets WHERE user_id = ?",
                    (uid,),
                ).fetchone()
                cur_balance = int(wallet_row["balance"]) if wallet_row else 0
                new_balance = cur_balance + int(order_row["credits"])
                conn.execute(
                    "UPDATE credit_wallets SET balance = ?, updated_at = ? WHERE user_id = ?",
                    (new_balance, now_iso, uid),
                )
                conn.execute(
                    """
                    INSERT INTO credit_ledger (
                        entry_id, user_id, delta, balance_after, reason, reference_id, metadata_json, created_at
                    )
                    VALUES (?, ?, ?, ?, 'paddle_charge', ?, ?, ?)
                    """,
                    (
                        f"led_{uuid.uuid4().hex[:12]}",
                        uid,
                        int(order_row["credits"]),
                        new_balance,
                        resolved_order_id,
                        json.dumps(
                            {
                                "package_id": order_row["package_id"],
                                "paddle_transaction_id": order_row["paddle_transaction_id"],
                                "event_id": event_id,
                            },
                            ensure_ascii=False,
                        ),
                        now_iso,
                    ),
                )
                conn.execute(
                    """
                    UPDATE billing_orders
                    SET status = 'completed', updated_at = ?, completed_at = ?
                    WHERE order_id = ?
                    """,
                    (now_iso, now_iso, resolved_order_id),
                )
                credited = True

            if event_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO paddle_webhook_events (
                        event_id, event_type, transaction_id, payload_json, processed_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        event_type or "transaction.completed",
                        paddle_transaction_id or order_row["paddle_transaction_id"],
                        payload_json or "{}",
                        now_iso,
                    ),
                )

            updated_order = conn.execute(
                "SELECT * FROM billing_orders WHERE order_id = ?",
                (resolved_order_id,),
            ).fetchone()
            updated_wallet = conn.execute(
                "SELECT * FROM credit_wallets WHERE user_id = ?",
                (uid,),
            ).fetchone()
        return (
            self._row_to_billing_order(updated_order),  # type: ignore[arg-type]
            credited,
            self._row_to_wallet(updated_wallet),  # type: ignore[arg-type]
        )

    def mark_billing_order_status(
        self,
        *,
        order_id: Optional[str] = None,
        paddle_transaction_id: Optional[str] = None,
        status: str,
        event_id: Optional[str] = None,
        event_type: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            row = None
            if order_id:
                row = conn.execute(
                    "SELECT * FROM billing_orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
            if row is None and paddle_transaction_id:
                row = conn.execute(
                    "SELECT * FROM billing_orders WHERE paddle_transaction_id = ?",
                    (paddle_transaction_id,),
                ).fetchone()
            if row is None:
                return None

            if row["status"] == "pending":
                conn.execute(
                    "UPDATE billing_orders SET status = ?, updated_at = ? WHERE order_id = ?",
                    (status, now_iso, row["order_id"]),
                )

            if event_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO paddle_webhook_events (
                        event_id, event_type, transaction_id, payload_json, processed_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        event_type or status,
                        paddle_transaction_id or row["paddle_transaction_id"],
                        payload_json or "{}",
                        now_iso,
                    ),
                )

            updated = conn.execute(
                "SELECT * FROM billing_orders WHERE order_id = ?",
                (row["order_id"],),
            ).fetchone()
        return self._row_to_billing_order(updated) if updated else None
