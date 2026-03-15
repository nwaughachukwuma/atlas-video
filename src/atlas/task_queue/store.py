"""
SQLite-backed task store with WAL mode for concurrent reads
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Optional

from .config import (
    DB_PATH,
    MAX_COMPLETED_TASKS,
    MAX_FAILED_TASKS,
    TASK_TIMEOUT,
    TaskStatus,
    now_iso,
)

_TASK_DDL = """\
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

_RUN_DDL = """\
CREATE TABLE IF NOT EXISTS runs (
    id               TEXT PRIMARY KEY,
    task_id          TEXT,
    command          TEXT NOT NULL,
    label            TEXT NOT NULL DEFAULT '',
    mode             TEXT NOT NULL DEFAULT 'direct',
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    finished_at      TEXT,
    input_path       TEXT,
    output_path      TEXT,
    user_output_path TEXT,
    benchmark_path   TEXT,
    log_path         TEXT,
    format           TEXT,
    error            TEXT,
    metadata_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_command ON runs(command);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_mode ON runs(mode);
"""


class _SQLiteStoreBase:
    """Base SQLite store with WAL-enabled thread-local connections."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._local = threading.local()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(self._ddl)

    @property
    def _ddl(self) -> str:
        raise NotImplementedError

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


class TaskStore(_SQLiteStoreBase):
    """SQLite-backed task store. WAL mode allows concurrent reads from any thread."""

    @property
    def _ddl(self) -> str:
        return _TASK_DDL

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


class RunStore(_SQLiteStoreBase):
    """SQLite-backed store for all transcribe/extract/index runs."""

    @property
    def _ddl(self) -> str:
        return _RUN_DDL

    def add(
        self,
        run_id: str,
        command: str,
        label: str,
        *,
        mode: str = "direct",
        status: str = TaskStatus.PENDING,
        task_id: str | None = None,
        input_path: str | None = None,
        output_path: str | None = None,
        user_output_path: str | None = None,
        benchmark_path: str | None = None,
        log_path: str | None = None,
        fmt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert a new run row."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO runs ("
                "id, task_id, command, label, mode, status, created_at, input_path, output_path, "
                "user_output_path, benchmark_path, log_path, format, metadata_json"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    task_id,
                    command,
                    label,
                    mode,
                    status,
                    now_iso(),
                    input_path,
                    output_path,
                    user_output_path,
                    benchmark_path,
                    log_path,
                    fmt,
                    json.dumps(metadata, default=str) if metadata is not None else None,
                ),
            )

    def mark_running(self, run_id: str) -> None:
        """mark running"""
        with self._tx() as conn:
            conn.execute(
                "UPDATE runs SET status=?, started_at=? WHERE id=?",
                (TaskStatus.RUNNING, now_iso(), run_id),
            )

    def mark_completed(
        self,
        run_id: str,
        *,
        output_path: str | None = None,
        benchmark_path: str | None = None,
        log_path: str | None = None,
        user_output_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """mark completed"""
        with self._tx() as conn:
            conn.execute(
                "UPDATE runs SET status=?, finished_at=?, output_path=COALESCE(?, output_path), "
                "benchmark_path=COALESCE(?, benchmark_path), log_path=COALESCE(?, log_path), "
                "user_output_path=COALESCE(?, user_output_path), metadata_json=COALESCE(?, metadata_json) "
                "WHERE id=?",
                (
                    TaskStatus.COMPLETED,
                    now_iso(),
                    output_path,
                    benchmark_path,
                    log_path,
                    user_output_path,
                    json.dumps(metadata, default=str) if metadata is not None else None,
                    run_id,
                ),
            )

    def mark_failed(
        self,
        run_id: str,
        error: str,
        *,
        output_path: str | None = None,
        benchmark_path: str | None = None,
        log_path: str | None = None,
        user_output_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """mark failed"""
        with self._tx() as conn:
            conn.execute(
                "UPDATE runs SET status=?, finished_at=?, error=?, output_path=COALESCE(?, output_path), "
                "benchmark_path=COALESCE(?, benchmark_path), log_path=COALESCE(?, log_path), "
                "user_output_path=COALESCE(?, user_output_path), metadata_json=COALESCE(?, metadata_json) "
                "WHERE id=?",
                (
                    TaskStatus.FAILED,
                    now_iso(),
                    error,
                    output_path,
                    benchmark_path,
                    log_path,
                    user_output_path,
                    json.dumps(metadata, default=str) if metadata is not None else None,
                    run_id,
                ),
            )

    def mark_timeout(
        self,
        run_id: str,
        error: str,
        *,
        output_path: str | None = None,
        benchmark_path: str | None = None,
        log_path: str | None = None,
        user_output_path: str | None = None,
    ) -> None:
        """mark timeout"""
        with self._tx() as conn:
            conn.execute(
                "UPDATE runs SET status=?, finished_at=?, error=?, output_path=COALESCE(?, output_path), "
                "benchmark_path=COALESCE(?, benchmark_path), log_path=COALESCE(?, log_path), "
                "user_output_path=COALESCE(?, user_output_path) WHERE id=?",
                (
                    TaskStatus.TIMEOUT,
                    now_iso(),
                    error,
                    output_path,
                    benchmark_path,
                    log_path,
                    user_output_path,
                    run_id,
                ),
            )

    def get(self, run_id: str) -> Optional[dict]:
        """get"""
        row = self._conn().execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._decode_row(row)

    def list_all(
        self,
        *,
        status: str | None = None,
        command: str | None = None,
        mode: str | None = None,
        limit: int | None = None,
    ) -> List[dict]:
        """list all"""
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if command:
            clauses.append("command=?")
            params.append(command)
        if mode:
            clauses.append("mode=?")
            params.append(mode)

        query = "SELECT * FROM runs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        rows = self._conn().execute(query, tuple(params)).fetchall()
        return [self._decode_row(r) for r in rows]

    def _decode_row(self, row: sqlite3.Row | None) -> Optional[dict]:
        if row is None:
            return None
        output = dict(row)
        metadata_json = output.pop("metadata_json", None)
        output["metadata"] = json.loads(metadata_json) if metadata_json else None
        return output
