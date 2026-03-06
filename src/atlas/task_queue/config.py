"""
Task queue configuration — constants, paths, and status enum
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from pathlib import Path

# ── Worker & timeout knobs ────────────────────────────────────────────────────

DEFAULT_WORKERS = 2
MAX_WORKERS = 2
TASK_TIMEOUT = 600  # seconds (10 minutes)
ATLAS_HOME = Path(os.environ.get("ATLAS_HOME", Path.home() / ".atlas"))
HEARTBEAT_INTERVAL = 10  # seconds between heartbeat checks

# ── Concurrency policy ────────────────────────────────────────────────────────

# Hard cap on total simultaneous workers.
MAX_CONCURRENT = 2
# extract + index share one slot — only one may run at a time.
HEAVY_CONCURRENCY = 1
# transcribe tasks may each fill a slot, up to this many simultaneously.
TRANSCRIBE_CONCURRENCY = 2
# Commands that count toward the "heavy" limit.
HEAVY_COMMANDS: frozenset[str] = frozenset({"extract", "index"})

# ── File-system paths ─────────────────────────────────────────────────────────

QUEUE_DIR = ATLAS_HOME / "queue"
DB_PATH = QUEUE_DIR / "tasks.db"
RESULTS_DIR = QUEUE_DIR / "queued_tasks" / "results"

# ── Retention limits ──────────────────────────────────────────────────────────

MAX_FAILED_TASKS = 150
MAX_COMPLETED_TASKS = 100


# ── Task status ───────────────────────────────────────────────────────────────


class TaskStatus(str, Enum):
    """Possible lifecycle states for a queued task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# ── Helpers ───────────────────────────────────────────────────────────────────


def now_iso() -> str:
    """Return the current local time as a compact ISO-8601 string."""
    return datetime.now().isoformat(timespec="seconds")
