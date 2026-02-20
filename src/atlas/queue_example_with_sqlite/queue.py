"""
queue.py — Lightweight, disk-backed, in-process task queue.

Design:
  • ProcessPoolExecutor runs tasks in real OS processes (bypasses GIL, one
    process per CPU core up to max_workers).
  • A single background *daemon* thread (QueueMonitor) polls the SQLite store
    for pending tasks and feeds them to the pool.
  • Completed tasks are deleted from the DB immediately; failed tasks are
    retained for inspection and cleaned on the next startup.
  • SIGINT / SIGTERM are intercepted to warn the user when active tasks exist.
  • No Redis, no external broker, no long-lived daemons.

Typical lifecycle:
    queue = TaskQueue()              # starts monitor thread + process pool
    queue.submit(encode_video, src, dst, label="Encode S01E01")
    queue.submit(encode_video, src2, dst2, label="Encode S01E02")
    # CLI returns immediately; background work continues.
    # System notification fires when each task finishes.
"""

import signal
import sys
import threading
import time
import uuid
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .notify import send as notify
from .store import TaskStore

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_WORKERS = 4
DEFAULT_DB_PATH = Path.home() / ".taskqueue" / "tasks.db"
POLL_INTERVAL = 0.5  # seconds between store polls in the monitor thread


# ── Worker-side execution (runs in a subprocess) ───────────────────────────────


def _execute_task(
    fn_module: str,
    fn_qualname: str,
    args: Tuple,
    kwargs: Dict,
    task_id: str,
    label: str,
    db_path: str,
) -> Tuple[str, bool, str]:
    """
    Top-level function executed inside a worker process.
    Must be importable (defined at module level, not a closure).
    Returns (task_id, success, message).
    """
    import importlib

    store = TaskStore(Path(db_path))
    store.mark_running(task_id)

    started = time.monotonic()
    try:
        # Re-import the callable in the worker process.
        module = importlib.import_module(fn_module)
        fn: Callable = module
        for attr in fn_qualname.split("."):
            fn = getattr(fn, attr)

        fn(*args, **kwargs)

        elapsed = time.monotonic() - started
        msg = f"Completed in {_fmt_duration(elapsed)}"
        store.mark_done(task_id)
        notify(f"✅ {label}", msg, success=True)
        return task_id, True, msg

    except Exception as exc:
        elapsed = time.monotonic() - started
        err = f"{type(exc).__name__}: {exc}"
        store.mark_failed(task_id, err)
        notify(f"❌ {label}", err[:120], success=False)
        return task_id, False, err


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"


# ── Queue monitor (background thread in the main process) ──────────────────────


class _QueueMonitor(threading.Thread):
    """
    Daemon thread that watches for pending tasks and submits them to the
    ProcessPoolExecutor. It does NOT poll SQLite on every tick; it wakes up
    only when a new task is submitted or the poll interval elapses.
    """

    def __init__(self, store: TaskStore, pool: ProcessPoolExecutor, max_workers: int):
        super().__init__(daemon=True, name="QueueMonitor")
        self._store = store
        self._pool = pool
        self._max_workers = max_workers
        self._pending: Dict[str, Tuple] = {}  # task_id → (fn_module, fn_qualname, args, kwargs, label)
        self._running: Dict[str, Future] = {}  # task_id → Future
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._stop = threading.Event()

    def enqueue(self, task_id: str, fn_module: str, fn_qualname: str, args: Tuple, kwargs: Dict, label: str) -> None:
        with self._lock:
            self._pending[task_id] = (fn_module, fn_qualname, args, kwargs, label)
        self._wakeup.set()

    def active_count(self) -> int:
        with self._lock:
            return len(self._pending) + len(self._running)

    def shutdown(self) -> None:
        self._stop.set()
        self._wakeup.set()

    def run(self) -> None:
        while not self._stop.is_set():
            self._wakeup.wait(timeout=POLL_INTERVAL)
            self._wakeup.clear()
            self._dispatch()
            self._reap()

    def _dispatch(self) -> None:
        with self._lock:
            available_slots = self._max_workers - len(self._running)
            to_submit = list(self._pending.items())[:available_slots]

        for task_id, (fn_module, fn_qualname, args, kwargs, label) in to_submit:
            db_path = str(self._store.db_path)
            future = self._pool.submit(
                _execute_task,
                fn_module,
                fn_qualname,
                args,
                kwargs,
                task_id,
                label,
                db_path,
            )
            with self._lock:
                self._pending.pop(task_id, None)
                self._running[task_id] = future

    def _reap(self) -> None:
        """Remove completed futures from the running dict."""
        with self._lock:
            done = [tid for tid, f in self._running.items() if f.done()]
            for tid in done:
                self._running.pop(tid)


# ── Public interface ───────────────────────────────────────────────────────────


class TaskQueue:
    """
    Simple, disk-backed task queue for long-running CLI work.

    Args:
        max_workers: Maximum number of concurrent worker processes (default 4).
        db_path:     Path to the SQLite database file.
                     Defaults to ~/.taskqueue/tasks.db

    Usage:
        queue = TaskQueue(max_workers=2)
        queue.submit(my_function, arg1, arg2, label="My task")
        # Returns immediately; system notification fires on completion.
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_WORKERS,
        db_path: Path = DEFAULT_DB_PATH,
    ):
        self._store = TaskStore(Path(db_path))
        self._pool = ProcessPoolExecutor(max_workers=max_workers)
        self._monitor = _QueueMonitor(self._store, self._pool, max_workers)
        self._monitor.start()

        # Clean up stale 'running' rows from a previous crashed session.
        self._recover_stale()

        # Register signal handlers for graceful-ish shutdown warnings.
        self._install_signal_handlers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(
        self,
        fn: Callable,
        *args: Any,
        label: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Enqueue a task. Returns a task ID immediately.

        The callable *fn* must be importable at module level in the worker
        process — i.e. a top-level function or a static/class method, not
        a lambda or a locally-defined closure.

        Args:
            fn:     The function to run in a worker process.
            *args:  Positional arguments forwarded to fn.
            label:  Human-readable name shown in system notifications.
            **kwargs: Keyword arguments forwarded to fn.

        Returns:
            A UUID4 string identifying the queued task.
        """
        task_id = str(uuid.uuid4())
        label = label or getattr(fn, "__name__", "task")

        # Resolve the callable to a (module, qualname) pair that can be
        # re-imported inside the worker process.
        fn_module = fn.__module__
        fn_qualname = fn.__qualname__

        if "<" in fn_qualname:
            raise ValueError(
                f"Cannot queue {fn!r}: it appears to be a lambda or closure. "
                "Only importable (module-level) functions are supported."
            )

        self._store.add(task_id, label)
        self._monitor.enqueue(task_id, fn_module, fn_qualname, args, kwargs, label)

        print(f"[queue] Queued '{label}' ({task_id[:8]}…)", file=sys.stderr)
        return task_id

    def active_count(self) -> int:
        """Number of tasks currently pending or running."""
        return self._monitor.active_count()

    def status(self, task_id: str) -> Optional[dict]:
        """Return the stored status for a task, or None if already cleared."""
        row = self._store.get(task_id)
        return dict(row) if row else None

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Block until all active tasks finish (or timeout expires).

        Returns True if all tasks completed, False if timed out.
        """
        deadline = time.monotonic() + timeout if timeout else None
        while self._monitor.active_count() > 0:
            if deadline and time.monotonic() > deadline:
                return False
            time.sleep(0.3)
        return True

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the queue. Optionally wait for running tasks."""
        self._monitor.shutdown()
        self._pool.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recover_stale(self) -> None:
        """
        On startup, any task still marked 'running' or 'pending' from a
        previous crashed session is reset to 'failed' with an explanatory
        error so the user knows to resubmit.
        """
        stale = self._store.all_active()
        if not stale:
            return
        print(
            f"[queue] ⚠️  Found {len(stale)} unfinished task(s) from a previous "
            "session. Marking as failed — please resubmit them.",
            file=sys.stderr,
        )
        for row in stale:
            self._store.mark_failed(row["id"], "Interrupted: process was killed")

    def _install_signal_handlers(self) -> None:
        """
        Intercept SIGINT (Ctrl-C) and SIGTERM to warn the user when active
        tasks would be abandoned. On second signal, exit immediately.
        """
        self._warned = False

        def _handler(signum: int, frame: Any) -> None:
            active = self._monitor.active_count()
            if active > 0 and not self._warned:
                self._warned = True
                sig_name = "Ctrl-C" if signum == signal.SIGINT else "SIGTERM"
                print(
                    f"\n[queue] ⚠️  {sig_name} received — {active} task(s) still "
                    "running in background workers.\n"
                    "         Press Ctrl-C again (or send SIGTERM) to force-quit "
                    "and abandon them, or wait for completion.\n",
                    file=sys.stderr,
                )
            else:
                print("\n[queue] Force-quitting. Background tasks abandoned.", file=sys.stderr)
                self._pool.shutdown(wait=False, cancel_futures=True)
                sys.exit(1)

        signal.signal(signal.SIGINT, _handler)
        try:
            signal.signal(signal.SIGTERM, _handler)
        except (OSError, ValueError):
            pass  # SIGTERM not available on Windows
