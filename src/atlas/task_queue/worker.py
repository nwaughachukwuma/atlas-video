"""Detached worker process — one task, one process, own interpreter.

Invoked by :class:`TaskQueue` as::

    python -m atlas.task_queue.worker <task_id>

The parent CLI process spawns this as a fully detached subprocess (new
session, stdin closed, stdout/stderr redirected to a log file) and returns
immediately. This module boots its own Python runtime, loads ``.env``,
reads the task from SQLite, dispatches to the appropriate ``_run_*``
function, and writes results/notifications when done.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from pathlib import Path
from time import perf_counter

from .config import RESULTS_DIR, TASK_TIMEOUT
from .helpers import serialize_result, write_file
from .notify import notify
from .store import RunStore, TaskStore
from ..logger import get_logger
from ..run_history import build_benchmark_summary

logger = get_logger("atlas:worker")


def _trigger_dispatch():
    """Attempt to start the next pending task after a worker slot opens."""
    try:
        from .queue import get_queue

        get_queue().dispatch_next()
    except Exception as exc:
        logger.warning("dispatch_next failed: %s", exc)


# Command → importable function (resolved lazily).
_COMMANDS: dict[str, str] = {
    "transcribe": "atlas.cli.tasks.run_transcribe",
    "extract": "atlas.cli.tasks.run_extract",
    "index": "atlas.cli.tasks.run_index",
}


# ── helpers ───────────────────────────────────────────────────────────────────


def _import_func(dotted_path: str):
    """Import a callable by its fully-qualified dotted path."""
    import importlib

    module_path, func_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def _write_benchmark(task_id: str, total_s: float | None = None) -> bool:
    """Write a benchmark summary as an ASCII table to benchmark.txt.

    Args:
        task_id: The task whose result directory receives the file.
        total_s: Optional wall-clock task runtime written below the table.
    """
    try:
        from ..benchmark import registry

        stats = registry.all_stats()
        if not stats:
            return False

        write_file(RESULTS_DIR / task_id / "benchmark.txt", build_benchmark_summary(stats, total_s=total_s))
        return True
    except Exception as exc:
        logger.warning("Failed to write benchmark for task %s: %s", task_id, exc)
        return False


# ── main entry point ─────────────────────────────────────────────────────────


def run_task(task_id: str) -> None:
    """Execute a single queued task (called once per subprocess)."""
    from dotenv import load_dotenv

    load_dotenv()

    store = TaskStore()
    run_store = RunStore(db_path=store.db_path)
    task = store.get(task_id)
    if not task:
        logger.error("Task %s not found in database", task_id)
        sys.exit(1)

    command: str = task["command"]
    output_path: str | None = task.get("output_path")
    benchmark: bool = bool(task.get("benchmark"))
    results_dir = RESULTS_DIR / task_id
    output_file = results_dir / "output.json"
    args_file = results_dir / "args.json"

    # Resolve the worker function.
    func_path = _COMMANDS.get(command)
    if not func_path:
        store.mark_failed(task_id, f"Unknown command: {command}")
        logger.error("Unknown command %r for task %s", command, task_id)
        return

    # Load serialised arguments.
    if not args_file.exists():
        store.mark_failed(task_id, "args.json missing — cannot reconstruct arguments")
        return

    args_dict = json.loads(args_file.read_text())
    args = argparse.Namespace(**args_dict)

    func = _import_func(func_path)
    store.mark_running(task_id)
    run_store.mark_running(task_id)
    logger.info("Worker started for task %s (%s)", task_id, command)

    t_start = perf_counter()
    # Enforce a hard timeout via a watchdog thread.
    timed_out = threading.Event()

    def _watchdog() -> None:
        timed_out.wait(TASK_TIMEOUT)
        if not timed_out.is_set():
            # Timeout reached — the main thread is still blocked.
            store.mark_timeout(task_id)
            run_store.mark_timeout(
                task_id,
                f"Exceeded {TASK_TIMEOUT}s timeout",
                output_path=str(output_file),
                benchmark_path=str(results_dir / "benchmark.txt") if benchmark else None,
                log_path=str(results_dir / "worker.log"),
                user_output_path=output_path,
            )
            write_file(output_file, json.dumps({"error": f"Exceeded {TASK_TIMEOUT}s timeout"}))
            if output_path:
                write_file(Path(output_path), json.dumps({"error": f"Exceeded {TASK_TIMEOUT}s timeout"}))
            notify(
                "Atlas Task Status",
                f"[timeout]: {command} ({task_id}) — exceeded {TASK_TIMEOUT}s",
                success=False,
            )
            logger.error("Task %s timed out after %ds", task_id, TASK_TIMEOUT)
            _trigger_dispatch()
            # Hard-exit the worker process.
            os._exit(1)

    timer = threading.Thread(target=_watchdog, daemon=True, name="atlas-watchdog")
    timer.start()

    try:
        result = func(args)
        # Cancel the watchdog.
        timed_out.set()

        content = serialize_result(result)
        store.mark_completed(task_id)
        write_file(output_file, content)
        if output_path:
            write_file(Path(output_path), content)
        benchmark_written = False
        if benchmark:
            benchmark_written = _write_benchmark(task_id, total_s=perf_counter() - t_start)
        run_store.mark_completed(
            task_id,
            output_path=str(output_file),
            benchmark_path=str(results_dir / "benchmark.txt") if benchmark and benchmark_written else None,
            log_path=str(results_dir / "worker.log"),
            user_output_path=output_path,
            metadata=result if isinstance(result, dict) else None,
        )
        notify(
            "Atlas Task Status",
            f"[completed]: {command} ({task_id}) finished successfully",
            success=True,
        )
        logger.info("Task %s completed", task_id)
        _trigger_dispatch()
    except Exception as exc:
        timed_out.set()  # cancel watchdog

        error_msg = f"{type(exc).__name__}: {exc}"
        store.mark_failed(task_id, error_msg)
        run_store.mark_failed(
            task_id,
            error_msg,
            output_path=str(output_file),
            benchmark_path=str(results_dir / "benchmark.txt") if benchmark else None,
            log_path=str(results_dir / "worker.log"),
            user_output_path=output_path,
        )
        write_file(output_file, json.dumps({"error": error_msg}))
        if output_path:
            write_file(Path(output_path), json.dumps({"error": error_msg}))
        notify(
            "Atlas Task Status",
            f"[failed]: {command} ({task_id}) — {error_msg[:120]}",
            success=False,
        )
        logger.error("Task %s failed: %s", task_id, error_msg)
        _trigger_dispatch()


# ── script entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m atlas.task_queue.worker <task_id>", file=sys.stderr)
        sys.exit(2)

    # Point root logger output to the worker log file.
    _task_id = sys.argv[1]
    _log_file = RESULTS_DIR / _task_id / "worker.log"
    _log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(_log_file),
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    run_task(_task_id)
