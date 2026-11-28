"""Atomic SQLite backup & restore to object storage (Cloudflare R2) across stateless Cloud Run restarts."""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

from .storage import LocalStorageBackend

logger = logging.getLogger("app.db_persistence")

SQLITE_STATE_OBJECT_KEY = "_state/napda_jobs.db"
SQLITE_MAGIC = b"SQLite format 3\x00"


def _is_remote_storage(storage: Any) -> bool:
    return (
        storage is not None
        and not isinstance(storage, LocalStorageBackend)
        and hasattr(storage, "download_file")
        and hasattr(storage, "upload_file")
    )


def _is_valid_sqlite_file(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    try:
        with path.open("rb") as fh:
            if fh.read(16) != SQLITE_MAGIC:
                return False
        conn = sqlite3.connect(str(path), timeout=5.0)
        try:
            row = conn.execute("PRAGMA quick_check").fetchone()
            return bool(row and row[0] == "ok")
        finally:
            conn.close()
    except Exception:
        return False


def hydrate_sqlite_from_storage(
    db_path: str | Path,
    storage: Any,
    *,
    object_key: str = SQLITE_STATE_OBJECT_KEY,
) -> bool:
    """Restore `db_path` from persistent remote storage on startup if local DB is absent."""
    db_str = str(db_path or "").strip()
    if not db_str or db_str == ":memory:" or not _is_remote_storage(storage):
        return False

    target = Path(db_str).expanduser().resolve()
    if target.is_file() and target.stat().st_size > 0:
        return False

    try:
        if hasattr(storage, "head_object") and storage.head_object(object_key) is None:
            return False
    except Exception as exc:
        logger.debug("SQLite remote state check skipped (%s): %s", object_key, exc)
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=".hydrate_db_", suffix=".sqlite", dir=str(target.parent))
    os.close(fd)
    tmp_path = Path(tmp_str)
    try:
        storage.download_file(object_key, tmp_path)
        if not _is_valid_sqlite_file(tmp_path):
            logger.warning("Downloaded SQLite snapshot (%s) failed integrity check; ignoring.", object_key)
            return False
        os.replace(tmp_path, target)
        logger.info("Hydrated SQLite database from remote storage (%s -> %s)", object_key, target)
        return True
    except Exception as exc:
        logger.warning("Failed to hydrate SQLite from remote storage (%s): %s", object_key, exc)
        return False
    finally:
        tmp_path.unlink(missing_ok=True)


class SqliteStorageSyncer:
    """Debounced online SQLite backup (`sqlite3.Connection.backup`) to persistent object storage."""

    def __init__(
        self,
        db_path: str | Path,
        storage: Any,
        *,
        object_key: str = SQLITE_STATE_OBJECT_KEY,
        debounce_sec: float = 2.0,
    ) -> None:
        self.db_str = str(db_path or "").strip()
        self.db_path = Path(self.db_str).expanduser().resolve() if self.db_str and self.db_str != ":memory:" else None
        self.storage = storage
        self.object_key = object_key
        self.debounce_sec = max(0.05, float(debounce_sec))
        self._flush_lock = threading.Lock()
        self._timer_lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._dirty = False

    @property
    def enabled(self) -> bool:
        return self.db_path is not None and _is_remote_storage(self.storage)

    def schedule_sync(self) -> None:
        """Queue a background debounced snapshot upload without blocking request threads."""
        if not self.enabled:
            return
        with self._timer_lock:
            self._dirty = True
            if self._timer is not None and self._timer.is_alive():
                return
            timer = threading.Timer(self.debounce_sec, self._timer_flush)
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _timer_flush(self) -> None:
        with self._timer_lock:
            self._timer = None
            dirty = self._dirty
            self._dirty = False
        if dirty:
            self.flush()

    def flush(self) -> bool:
        """Take an online consistent SQLite backup and upload it to remote storage."""
        if not self.enabled or self.db_path is None:
            return False
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._dirty = False

        if not self.db_path.is_file() or self.db_path.stat().st_size <= 0:
            return False

        with self._flush_lock:
            tmp_path: Optional[Path] = None
            src_conn: Optional[sqlite3.Connection] = None
            dst_conn: Optional[sqlite3.Connection] = None
            try:
                fd, tmp_str = tempfile.mkstemp(
                    prefix=".backup_db_",
                    suffix=".sqlite",
                    dir=str(self.db_path.parent),
                )
                os.close(fd)
                tmp_path = Path(tmp_str)

                src_conn = sqlite3.connect(str(self.db_path), timeout=30.0)
                dst_conn = sqlite3.connect(str(tmp_path), timeout=30.0)
                src_conn.backup(dst_conn)
                dst_conn.close()
                dst_conn = None
                src_conn.close()
                src_conn = None

                self.storage.upload_file(tmp_path, self.object_key)
                return True
            except Exception as exc:
                logger.warning("Failed to backup SQLite to remote storage (%s): %s", self.object_key, exc)
                return False
            finally:
                if dst_conn is not None:
                    try:
                        dst_conn.close()
                    except Exception:
                        pass
                if src_conn is not None:
                    try:
                        src_conn.close()
                    except Exception:
                        pass
                if tmp_path is not None:
                    tmp_path.unlink(missing_ok=True)
