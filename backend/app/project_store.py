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

                CREATE TABLE IF NOT EXISTS api_usage_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    user_id TEXT,
                    project_id TEXT,
                    job_id TEXT,
                    hook_type TEXT,
                    stage TEXT NOT NULL,
                    step_name TEXT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    thinking_tokens INTEGER NOT NULL DEFAULT 0,
                    media_unit TEXT,
                    media_qty REAL,
                    estimated_cost_usd REAL,
                    unit_price_label TEXT,
                    pricing_version TEXT NOT NULL DEFAULT '2026-11',
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'ok',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_api_usage_created
                    ON api_usage_events(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_api_usage_project
                    ON api_usage_events(project_id, created_at ASC);
                CREATE INDEX IF NOT EXISTS idx_api_usage_provider_model
                    ON api_usage_events(provider, model, created_at DESC);
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

    def deduct_wallet_credits(self, user_id: str, amount: int) -> bool:
        """Atomically deduct `amount` credits from user's wallet if balance is sufficient."""
        amt = int(amount)
        if amt <= 0:
            return True
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE credit_wallets
                SET balance = balance - ?, updated_at = ?
                WHERE user_id = ? AND balance >= ?
                """,
                (amt, now_iso, user_id, amt),
            )
        return cur.rowcount > 0

    def refund_wallet_credits(
        self, user_id: str, amount: int, *, default_free_videos: int = 0
    ) -> Dict[str, Any]:
        """Atomically refund `amount` credits back to user's wallet."""
        amt = max(0, int(amount))
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
            if amt > 0:
                conn.execute(
                    """
                    UPDATE credit_wallets
                    SET balance = balance + ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (amt, now_iso, user_id),
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

    @staticmethod
    def _row_to_usage_event(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "created_at": row["created_at"],
            "user_id": row["user_id"],
            "project_id": row["project_id"],
            "job_id": row["job_id"],
            "hook_type": row["hook_type"],
            "stage": row["stage"],
            "step_name": row["step_name"],
            "provider": row["provider"],
            "model": row["model"],
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "cached_tokens": int(row["cached_tokens"] or 0),
            "thinking_tokens": int(row["thinking_tokens"] or 0),
            "media_unit": row["media_unit"],
            "media_qty": float(row["media_qty"]) if row["media_qty"] is not None else None,
            "estimated_cost_usd": float(row["estimated_cost_usd"]) if row["estimated_cost_usd"] is not None else None,
            "unit_price_label": row["unit_price_label"],
            "pricing_version": row["pricing_version"],
            "latency_ms": int(row["latency_ms"] or 0),
            "cache_hit": bool(row["cache_hit"]),
            "status": row["status"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def record_api_usage(
        self,
        *,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        job_id: Optional[str] = None,
        hook_type: Optional[str] = None,
        stage: str,
        step_name: Optional[str] = None,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        thinking_tokens: int = 0,
        media_unit: Optional[str] = None,
        media_qty: Optional[float] = None,
        estimated_cost_usd: Optional[float] = None,
        unit_price_label: Optional[str] = None,
        pricing_version: str = "2026-11",
        latency_ms: int = 0,
        cache_hit: bool = False,
        status: str = "ok",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event_id = f"usg_{uuid.uuid4().hex[:14]}"
        now_iso = _now_utc().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_usage_events (
                    event_id, created_at, user_id, project_id, job_id, hook_type,
                    stage, step_name, provider, model,
                    input_tokens, output_tokens, cached_tokens, thinking_tokens,
                    media_unit, media_qty, estimated_cost_usd, unit_price_label, pricing_version,
                    latency_ms, cache_hit, status, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    now_iso,
                    user_id,
                    project_id,
                    job_id,
                    hook_type,
                    stage,
                    step_name,
                    provider,
                    model,
                    int(input_tokens or 0),
                    int(output_tokens or 0),
                    int(cached_tokens or 0),
                    int(thinking_tokens or 0),
                    media_unit,
                    float(media_qty) if media_qty is not None else None,
                    float(estimated_cost_usd) if estimated_cost_usd is not None else None,
                    unit_price_label,
                    pricing_version,
                    max(0, int(latency_ms or 0)),
                    1 if cache_hit else 0,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            row = conn.execute("SELECT * FROM api_usage_events WHERE event_id = ?", (event_id,)).fetchone()
        return self._row_to_usage_event(row)  # type: ignore[arg-type]

    def get_usage_summary(self, *, days: int = 30, limit_projects: int = 50) -> Dict[str, Any]:
        since_iso = (_now_utc() - timedelta(days=max(1, int(days)))).isoformat()
        with self._lock, self._connect() as conn:
            t_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                    COALESCE(SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END), 0) AS error_calls,
                    COUNT(DISTINCT NULLIF(project_id, '')) AS project_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                    COALESCE(SUM(thinking_tokens), 0) AS thinking_tokens,
                    COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd,
                    COALESCE(SUM(CASE WHEN estimated_cost_usd IS NULL AND cache_hit = 0 THEN 1 ELSE 0 END), 0) AS unpriced_calls
                FROM api_usage_events
                WHERE created_at >= ?
                """,
                (since_iso,),
            ).fetchone()

            pm_rows = conn.execute(
                """
                SELECT
                    provider,
                    model,
                    COUNT(*) AS calls,
                    COALESCE(SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                    COUNT(DISTINCT NULLIF(project_id, '')) AS project_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(thinking_tokens), 0) AS thinking_tokens,
                    COALESCE(SUM(media_qty), 0.0) AS media_qty,
                    MAX(media_unit) AS media_unit,
                    MAX(CASE WHEN cache_hit = 0 THEN unit_price_label ELSE NULL END) AS unit_price_label,
                    COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd,
                    COALESCE(SUM(CASE WHEN estimated_cost_usd IS NULL AND cache_hit = 0 THEN 1 ELSE 0 END), 0) AS unpriced_calls,
                    COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms
                FROM api_usage_events
                WHERE created_at >= ?
                GROUP BY provider, model
                ORDER BY estimated_cost_usd DESC, calls DESC
                """,
                (since_iso,),
            ).fetchall()

            stage_rows = conn.execute(
                """
                SELECT
                    stage,
                    COUNT(*) AS calls,
                    COALESCE(SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(thinking_tokens), 0) AS thinking_tokens,
                    MAX(media_unit) AS media_unit,
                    COALESCE(SUM(media_qty), 0.0) AS media_qty,
                    COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd,
                    COALESCE(SUM(CASE WHEN estimated_cost_usd IS NULL AND cache_hit = 0 THEN 1 ELSE 0 END), 0) AS unpriced_calls,
                    COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms
                FROM api_usage_events
                WHERE created_at >= ?
                GROUP BY stage
                ORDER BY estimated_cost_usd DESC, calls DESC
                """,
                (since_iso,),
            ).fetchall()

            proj_rows = conn.execute(
                """
                SELECT
                    e.project_id,
                    MAX(e.user_id) AS user_id,
                    COALESCE(MAX(u.email), '') AS user_email,
                    MAX(p.product_json) AS product_json,
                    MAX(p.status) AS project_status,
                    GROUP_CONCAT(DISTINCT NULLIF(e.hook_type, '')) AS hook_types,
                    GROUP_CONCAT(DISTINCT e.provider) AS providers,
                    GROUP_CONCAT(DISTINCT e.model) AS models,
                    COUNT(*) AS calls,
                    COALESCE(SUM(CASE WHEN e.cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                    COALESCE(SUM(e.input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(e.output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(e.thinking_tokens), 0) AS thinking_tokens,
                    COALESCE(SUM(CASE WHEN e.media_unit = 'sec' THEN e.media_qty ELSE 0.0 END), 0.0) AS video_sec,
                    COALESCE(SUM(CASE WHEN e.media_unit = 'image' THEN e.media_qty ELSE 0.0 END), 0.0) AS image_count,
                    COALESCE(SUM(CASE WHEN e.media_unit = 'char' THEN e.media_qty ELSE 0.0 END), 0.0) AS tts_chars,
                    COALESCE(SUM(e.estimated_cost_usd), 0.0) AS estimated_cost_usd,
                    COALESCE(SUM(CASE WHEN e.estimated_cost_usd IS NULL AND e.cache_hit = 0 THEN 1 ELSE 0 END), 0) AS unpriced_calls,
                    COALESCE(SUM(e.latency_ms), 0) AS total_latency_ms,
                    MAX(e.created_at) AS last_event_at
                FROM api_usage_events e
                LEFT JOIN projects p ON p.id = e.project_id
                LEFT JOIN users u ON u.user_id = COALESCE(p.user_id, e.user_id)
                WHERE e.created_at >= ? AND e.project_id IS NOT NULL AND e.project_id != ''
                GROUP BY e.project_id
                ORDER BY last_event_at DESC
                LIMIT ?
                """,
                (since_iso, max(1, int(limit_projects))),
            ).fetchall()

        totals = {
            "total_calls": int(t_row["total_calls"] or 0),
            "cache_hits": int(t_row["cache_hits"] or 0),
            "error_calls": int(t_row["error_calls"] or 0),
            "project_count": int(t_row["project_count"] or 0),
            "input_tokens": int(t_row["input_tokens"] or 0),
            "output_tokens": int(t_row["output_tokens"] or 0),
            "cached_tokens": int(t_row["cached_tokens"] or 0),
            "thinking_tokens": int(t_row["thinking_tokens"] or 0),
            "estimated_cost_usd": round(float(t_row["estimated_cost_usd"] or 0.0), 6),
            "unpriced_calls": int(t_row["unpriced_calls"] or 0),
        }

        by_provider_model: List[Dict[str, Any]] = []
        for r in pm_rows:
            p_cnt = int(r["project_count"] or 0)
            est = round(float(r["estimated_cost_usd"] or 0.0), 6)
            by_provider_model.append(
                {
                    "provider": r["provider"],
                    "model": r["model"],
                    "calls": int(r["calls"] or 0),
                    "cache_hits": int(r["cache_hits"] or 0),
                    "project_count": p_cnt,
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "thinking_tokens": int(r["thinking_tokens"] or 0),
                    "media_unit": r["media_unit"],
                    "media_qty": round(float(r["media_qty"] or 0.0), 3),
                    "unit_price_label": r["unit_price_label"] or "단가 미등록",
                    "estimated_cost_usd": est,
                    "avg_cost_per_project_usd": round(est / p_cnt, 6) if p_cnt > 0 else est,
                    "unpriced_calls": int(r["unpriced_calls"] or 0),
                    "avg_latency_ms": int(round(float(r["avg_latency_ms"] or 0.0))),
                }
            )

        by_stage: List[Dict[str, Any]] = []
        for r in stage_rows:
            by_stage.append(
                {
                    "stage": r["stage"],
                    "calls": int(r["calls"] or 0),
                    "cache_hits": int(r["cache_hits"] or 0),
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "thinking_tokens": int(r["thinking_tokens"] or 0),
                    "media_unit": r["media_unit"],
                    "media_qty": round(float(r["media_qty"] or 0.0), 3),
                    "estimated_cost_usd": round(float(r["estimated_cost_usd"] or 0.0), 6),
                    "unpriced_calls": int(r["unpriced_calls"] or 0),
                    "avg_latency_ms": int(round(float(r["avg_latency_ms"] or 0.0))),
                }
            )

        recent_projects: List[Dict[str, Any]] = []
        for r in proj_rows:
            product_name = r["project_id"]
            if r["product_json"]:
                try:
                    pdata = json.loads(r["product_json"])
                    if isinstance(pdata, dict) and pdata.get("name"):
                        product_name = str(pdata["name"])
                except ValueError:
                    pass
            recent_projects.append(
                {
                    "project_id": r["project_id"],
                    "product_name": product_name,
                    "project_status": r["project_status"],
                    "user_id": r["user_id"],
                    "user_email": r["user_email"],
                    "hook_types": [x for x in (r["hook_types"] or "").split(",") if x],
                    "providers": [x for x in (r["providers"] or "").split(",") if x],
                    "models": [x for x in (r["models"] or "").split(",") if x],
                    "calls": int(r["calls"] or 0),
                    "cache_hits": int(r["cache_hits"] or 0),
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "thinking_tokens": int(r["thinking_tokens"] or 0),
                    "video_sec": round(float(r["video_sec"] or 0.0), 2),
                    "image_count": int(round(float(r["image_count"] or 0.0))),
                    "tts_chars": int(round(float(r["tts_chars"] or 0.0))),
                    "estimated_cost_usd": round(float(r["estimated_cost_usd"] or 0.0), 6),
                    "unpriced_calls": int(r["unpriced_calls"] or 0),
                    "total_latency_ms": int(r["total_latency_ms"] or 0),
                    "last_event_at": r["last_event_at"],
                }
            )

        return {
            "totals": totals,
            "by_provider_model": by_provider_model,
            "by_stage": by_stage,
            "recent_projects": recent_projects,
        }

    def get_project_usage_detail(self, project_id: str) -> Dict[str, Any]:
        project = self.get_project(project_id)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM api_usage_events
                WHERE project_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (project_id,),
            ).fetchall()
        events = [self._row_to_usage_event(r) for r in rows]
        totals = {
            "total_calls": len(events),
            "cache_hits": sum(1 for e in events if e["cache_hit"]),
            "input_tokens": sum(e["input_tokens"] for e in events),
            "output_tokens": sum(e["output_tokens"] for e in events),
            "cached_tokens": sum(e["cached_tokens"] for e in events),
            "thinking_tokens": sum(e["thinking_tokens"] for e in events),
            "estimated_cost_usd": round(
                sum(float(e["estimated_cost_usd"] or 0.0) for e in events), 6
            ),
            "unpriced_calls": sum(
                1 for e in events if e["estimated_cost_usd"] is None and not e["cache_hit"]
            ),
            "total_latency_ms": sum(e["latency_ms"] for e in events),
        }
        return {
            "project_id": project_id,
            "project": {
                "project_id": project["project_id"],
                "user_id": project["user_id"],
                "status": project["status"],
                "product_name": (project.get("product") or {}).get("name"),
            }
            if project
            else None,
            "totals": totals,
            "events": events,
        }

    def list_usage_events(
        self,
        *,
        limit: int = 100,
        project_id: Optional[str] = None,
        provider: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(500, int(limit))))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM api_usage_events
                {where_sql}
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._row_to_usage_event(r) for r in rows]
