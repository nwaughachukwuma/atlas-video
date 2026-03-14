"""
Subprocess-backed task queue — each task runs in its own Python process
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from uuid import uuid4

from .config import (
    HEAVY_COMMANDS,
    HEAVY_CONCURRENCY,
    MAX_CONCURRENT,
    RESULTS_DIR,
    TASK_TIMEOUT,
    TRANSCRIBE_CONCURRENCY,
)
from .helpers import worker_log_file_for
from .store import TaskStore
from ..logger import get_logger

logger = get_logger("atlas:queue")


class TaskQueue:
    """SQLite-backed task queue that spawns detached worker subprocesses.

    Each submitted task runs in its own Python interpreter via
    ``python -m atlas.task_queue.worker <task_id>``. The parent process
    returns immediately — no threads, no waiting.

    Args:
        db_path: optional path to SQLite database file; defaults to ``~/.atlas/queue/tasks.db``

    Usage::
        queue = get_queue()
        tid = queue.submit(
            args,
            command="transcribe",
            label="transcribe video.mp4",
        )
        # Returns immediately. Worker writes output, updates SQLite,
        # and fires a system notification on completion/failure.
    """

    def __init__(self, *, db_path: Path | None = None) -> None:
        self._store = TaskStore(db_path) if db_path else TaskStore()
        from ..settings import settings

        self._max_workers = settings.max_queue_workers

        # Clean up leftovers from a crashed previous session. Only marks
        # tasks that have been pending/running far longer than the timeout
        # so we never nuke a task that a live worker is still processing.
        self._recover_stale()

    # ── public API ────────────────────────────────────────────────────

    def submit(
        self,
        args: Any,
        *,
        command: str = "task",
        label: str = "",
        output_path: Optional[str] = None,
        benchmark: bool = False,
    ) -> str:
        """Enqueue a task. Returns a short task ID.

        *args* must be an ``argparse.Namespace`` (or any object whose
        ``vars()`` produces a JSON-serialisable dict). The worker
        subprocess reconstructs it and dispatches based on *command*.
        """
        task_id = uuid4().hex[:8]
        label = label or command

        # Prepare the results directory and serialise arguments.
        results_dir = RESULTS_DIR / task_id
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "args.json").write_text(
            json.dumps(vars(args) if hasattr(args, "__dict__") else {}, default=str),
        )

        self._store.add(task_id, command, label, output_path, benchmark)

        # Dispatch immediately if a slot is open; otherwise the task stays
        # pending and will be picked up when a running worker finishes.
        self.dispatch_next()

        logger.info("Queued task %s (%s): %s", task_id, command, label)
        return task_id

    def get_task(self, task_id: str) -> Optional[dict]:
        """Look up a task by *task_id*."""
        return self._store.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[dict]:
        """List tasks, optionally filtered by *status*."""
        return self._store.list_all(status)

    def active_count(self) -> int:
        """Number of pending + running tasks."""
        return self._store.active_count()

    # ── concurrency-aware dispatch ──────────────────────────────────────

    def dispatch_next(self) -> list[str]:
        """Spawn eligible pending tasks within the concurrency policy.

        Rules:
        * Total running workers ≤ MAX_CONCURRENT (2).
        * extract + index combined ≤ HEAVY_CONCURRENCY (1).
        * transcribe ≤ TRANSCRIBE_CONCURRENCY (2).

        Returns the list of task IDs whose workers were spawned.
        """
        counts = self._store.running_counts()
        total = sum(counts.values())
        heavy = sum(counts.get(cmd, 0) for cmd in HEAVY_COMMANDS)
        transcribe = counts.get("transcribe", 0)

        dispatched: list[str] = []
        for task in self._store.list_pending():
            if total >= MAX_CONCURRENT:
                break
            cmd = task["command"]
            if cmd in HEAVY_COMMANDS:
                if heavy >= HEAVY_CONCURRENCY:
                    continue
                self._spawn_worker(task["id"])
                dispatched.append(task["id"])
                heavy += 1
                total += 1
            elif cmd == "transcribe":
                if transcribe >= TRANSCRIBE_CONCURRENCY:
                    continue
                self._spawn_worker(task["id"])
                dispatched.append(task["id"])
                transcribe += 1
                total += 1
            else:
                # Unknown command type — spawn if there's a free slot.
                self._spawn_worker(task["id"])
                dispatched.append(task["id"])
                total += 1

        if dispatched:
            logger.info("Dispatched %d pending task(s): %s", len(dispatched), dispatched)
        return dispatched

    # ── subprocess spawning ───────────────────────────────────────────

    def _spawn_worker(self, task_id: str) -> None:
        """Launch ``python -m atlas.task_queue.worker <task_id>`` as a detached process."""
        log_file = worker_log_file_for(task_id)

        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": log_file.open("w"),
            "stderr": subprocess.STDOUT,
        }

        if sys.platform != "win32":
            kwargs["start_new_session"] = True
        else:
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]

        subprocess.Popen(
            [sys.executable, "-m", "atlas.task_queue.worker", task_id],
            **kwargs,
        )

    # ── stale recovery ────────────────────────────────────────────────

    def _recover_stale(self) -> None:
        """Mark genuinely stale tasks as failed.

        Only considers tasks whose ``started_at`` exceeds *TASK_TIMEOUT + 5 min*
        so that a long-running task from an active worker is never clobbered.
        Pending tasks older than the timeout are also recovered.
        """
        stale: list[dict] = []
        for task in self._store.stale_tasks():
            started = task.get("started_at")
            if started:
                age = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
                if age < TASK_TIMEOUT + 300:
                    continue  # might still be running in another process
            stale.append(task)

        if not stale:
            return

        logger.warning(
            "Found %d stale task(s) from a previous session — marking as failed",
            len(stale),
        )
        for task in stale:
            self._store.mark_failed(task["id"], "Interrupted: previous session ended")


# ── global singleton ──────────────────────────────────────────────────────────

_queue: Optional[TaskQueue] = None


def get_queue() -> TaskQueue:
    """Return (or create) the process-wide ``TaskQueue`` singleton."""
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
