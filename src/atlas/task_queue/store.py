"""
SQLite-backed task store with WAL mode for concurrent reads
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from .config import (
    DB_PATH,
    MAX_COMPLETED_TASKS,
    MAX_FAILED_TASKS,
    TASK_TIMEOUT,
    TaskStatus,
    now_iso,
)

_DDL = """\
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    command     TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    error       TEXT,
    output_path TEXT,
    benchmark   INTEGER NOT NULL DEFAULT 0
);
"""


class TaskStore:
    """SQLite-backed task store. WAL mode allows concurrent reads from any thread."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._local = threading.local()  # per-instance thread-local storage
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_DDL)

    # ── connection helpers ────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        """Return a thread-local connection with WAL enabled."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    @contextmanager
    def _tx(self):
        """Yield a connection inside a begin/commit block with rollback on error."""
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    # ── mutations ─────────────────────────────────────────────────────

    def add(
        self,
        task_id: str,
        command: str,
        label: str,
        output_path: Optional[str] = None,
        benchmark: bool = False,
    ) -> None:
        """Insert a new task row."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO tasks (id, command, label, status, created_at, output_path, benchmark)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, command, label, TaskStatus.PENDING, now_iso(), output_path, int(benchmark)),
            )

    def mark_running(self, task_id: str) -> None:
        """Transition task to running."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, started_at=? WHERE id=?",
                (TaskStatus.RUNNING, now_iso(), task_id),
            )

    def mark_completed(self, task_id: str) -> None:
        """Transition task to completed; trim old records."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, finished_at=? WHERE id=?",
                (TaskStatus.COMPLETED, now_iso(), task_id),
            )
            self._trim(conn)

    def mark_failed(self, task_id: str, error: str) -> None:
        """Transition task to failed with error message; trim old records."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, finished_at=?, error=? WHERE id=?",
                (TaskStatus.FAILED, now_iso(), error, task_id),
            )
            self._trim(conn)

    def mark_timeout(self, task_id: str) -> None:
        """Transition task to timeout."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, finished_at=?, error=? WHERE id=?",
                (TaskStatus.TIMEOUT, now_iso(), f"Exceeded {TASK_TIMEOUT}s timeout", task_id),
            )

    # ── queries ───────────────────────────────────────────────────────

    def get(self, task_id: str) -> Optional[dict]:
        """Return a single task dict or ``None``."""
        row = self._conn().execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_all(self, status: Optional[str] = None) -> List[dict]:
        """Return all tasks, optionally filtered by *status*."""
        if status:
            rows = (
                self._conn()
                .execute(
                    "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC",
                    (status,),
                )
                .fetchall()
            )
        else:
            rows = self._conn().execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_running(self) -> List[dict]:
        """Return tasks currently in *running* status."""
        rows = self._conn().execute("SELECT * FROM tasks WHERE status=?", (TaskStatus.RUNNING,)).fetchall()
        return [dict(r) for r in rows]

    def active_count(self) -> int:
        """Count of pending + running tasks."""
        row = self._conn().execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending', 'running')").fetchone()
        return row[0]

    def list_pending(self) -> List[dict]:
        """Return tasks with status=pending, oldest first (FIFO dispatch order)."""
        rows = self._conn().execute("SELECT * FROM tasks WHERE status='pending' ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]

    def running_counts(self) -> dict[str, int]:
        """Return a mapping of command → number of currently running tasks."""
        rows = (
            self._conn()
            .execute("SELECT command, COUNT(*) AS cnt FROM tasks WHERE status='running' GROUP BY command")
            .fetchall()
        )
        return {r["command"]: r["cnt"] for r in rows}

    def stale_tasks(self) -> List[dict]:
        """Tasks stuck in pending/running from a previous crashed session."""
        rows = self._conn().execute("SELECT * FROM tasks WHERE status IN ('pending', 'running')").fetchall()
        return [dict(r) for r in rows]

    # ── housekeeping ──────────────────────────────────────────────────

    def _trim(self, conn: sqlite3.Connection) -> None:
        """Keep only the newest MAX_COMPLETED_TASKS / MAX_FAILED_TASKS rows."""
        conn.execute(
            "DELETE FROM tasks WHERE id IN ("
            "  SELECT id FROM tasks WHERE status='completed'"
            "  ORDER BY finished_at DESC LIMIT -1 OFFSET ?"
            ")",
            (MAX_COMPLETED_TASKS,),
        )
        conn.execute(
            "DELETE FROM tasks WHERE id IN ("
            "  SELECT id FROM tasks WHERE status='failed'"
            "  ORDER BY finished_at DESC LIMIT -1 OFFSET ?"
            ")",
            (MAX_FAILED_TASKS,),
        )
