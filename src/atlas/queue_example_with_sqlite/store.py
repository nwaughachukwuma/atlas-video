"""
store.py — SQLite-backed task store.
WAL mode allows concurrent reads from worker processes without locking.
Completed tasks are deleted immediately to keep the DB lean.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    error       TEXT
);
"""

# One connection per thread to satisfy sqlite3's thread-safety rules.
_local = threading.local()


class TaskStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Initialise schema on a fresh connection so the file is created.
        with self._conn() as conn:
            conn.executescript(_DDL)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        """Return a thread-local connection with WAL enabled."""
        conn = getattr(_local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _local.conn = conn
        return conn

    @contextmanager
    def _tx(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, task_id: str, label: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO tasks (id, label, status, created_at) VALUES (?, ?, ?, ?)",
                (task_id, label, Status.PENDING, datetime.utcnow().isoformat()),
            )

    def mark_running(self, task_id: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, started_at=? WHERE id=?",
                (Status.RUNNING, datetime.utcnow().isoformat(), task_id),
            )

    def mark_done(self, task_id: str) -> None:
        """Mark complete then immediately delete — queue stays lean."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, finished_at=? WHERE id=?",
                (Status.DONE, datetime.utcnow().isoformat(), task_id),
            )
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, finished_at=?, error=? WHERE id=?",
                (Status.FAILED, datetime.utcnow().isoformat(), error, task_id),
            )
            # Keep failed rows so the user can inspect them; they can call
            # clear_failed() explicitly or they're cleaned on next startup.
            # Swap the line below in if you prefer auto-delete on failure:
            # conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def get(self, task_id: str) -> Optional[sqlite3.Row]:
        return self._conn().execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    def active_count(self) -> int:
        """Pending + running tasks."""
        row = self._conn().execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending','running')").fetchone()
        return row[0]

    def all_active(self) -> list:
        return (
            self._conn()
            .execute("SELECT * FROM tasks WHERE status IN ('pending','running') ORDER BY created_at")
            .fetchall()
        )

    def clear_failed(self) -> int:
        with self._tx() as conn:
            n = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]
            conn.execute("DELETE FROM tasks WHERE status='failed'")
        return n
