"""CLI sub-commands for ``atlas queue list`` and ``atlas queue status``."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import RESULTS_DIR
from .store import TaskStore

_STATUS_COLORS = {
    "pending": "yellow",
    "running": "cyan",
    "completed": "green",
    "failed": "red",
    "timeout": "magenta",
}


# ── Parser registration ──────────────────────────────────────────────────────


def add_queue_commands(subparsers: Any) -> None:
    """Register ``atlas queue list`` and ``atlas queue status`` sub-commands."""
    p_queue = subparsers.add_parser(
        "queue",
        help="Manage the task queue.",
        description="View and manage background tasks (transcribe / extract / index).",
        epilog=(
            "Examples:\n"
            "  atlas queue list\n"
            "  atlas queue list --status pending\n"
            "  atlas queue status --task-id abc12345\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p_queue.add_subparsers(dest="queue_command", metavar="<action>")
    sub.required = True

    # atlas queue list
    p_list = sub.add_parser("list", help="List tasks in the queue.")
    p_list.add_argument(
        "--status",
        "-s",
        choices=["pending", "running", "completed", "failed", "timeout"],
        help="Filter by status.",
    )
    p_list.set_defaults(func=cmd_queue_list)

    # atlas queue status
    p_status = sub.add_parser("status", help="Show status of a specific task.")
    p_status.add_argument("--task-id", "-t", required=True, help="Task ID to check.")
    p_status.set_defaults(func=cmd_queue_status)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _duration_str(started: str | None, finished: str | None) -> str:
    """Return a human-readable elapsed duration, or empty string if unavailable."""
    if not started or not finished:
        return ""
    try:
        secs = int((datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds())
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m {secs % 60}s"
    except Exception:
        return ""


def _parse_benchmark_file(path: Path) -> list[tuple[str, ...]]:
    """Parse the pipe-table benchmark.txt and return data rows (excluding header).

    Each returned tuple has six elements:
    (Function, Calls, Total (s), Avg (s), Min (s), Max (s))
    """
    rows: list[tuple[str, ...]] = []
    header_seen = False
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue  # skip title, separator lines
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 6:
            continue
        if not header_seen:
            header_seen = True  # skip the header row itself
            continue
        rows.append(tuple(cells))
    return rows


# ── Handlers ──────────────────────────────────────────────────────────────────


def cmd_queue_list(args: argparse.Namespace) -> None:
    """Print a JSON list of tasks in the queue."""
    import json

    store = TaskStore()
    status = getattr(args, "status", None)
    tasks = store.list_all(status)

    output = {
        "status_filter": status,
        "count": len(tasks),
        "tasks": tasks,
    }
    print(json.dumps(output, indent=2, default=str))


def cmd_queue_status(args: argparse.Namespace) -> None:
    """Print detailed status for a single task as JSON."""
    import json

    store = TaskStore()
    task = store.get(args.task_id)

    if not task:
        print(json.dumps({"error": f"Task {args.task_id} not found"}))
        return

    results_dir = RESULTS_DIR / task["id"]
    output_file = results_dir / "output.json"
    benchmark_file = results_dir / "benchmark.txt"

    output = dict(task)
    output["duration"] = _duration_str(task.get("started_at"), task.get("finished_at")) or None

    output["output_path"] = str(output_file)
    # Expose benchmark path instead of inlining the table.
    has_benchmark = bool(output.pop("benchmark", False))
    if has_benchmark:
        output["benchmark_path"] = str(benchmark_file)

    print(json.dumps(output, indent=2, default=str))
