"""
SQLite-backed task queue with subprocess workers.

Design
~~~~~~
* SQLite (WAL mode) for task persistence — survives process restarts.
* Each task runs in its own detached Python subprocess via
  ``python -m atlas.task_queue.worker <task_id>``. The parent CLI
  returns immediately.
* Workers handle their own timeout enforcement (watchdog thread).
* Completed tasks (last 25) and failed tasks (last 50) are retained for
  inspection; everything else is trimmed automatically.
* Results written to ``~/.atlas/queue/queued_tasks/results/{task_id}/output.txt``.
* Cross-platform system notifications on completion/failure/timeout.
* No Redis, no external broker, no long-lived daemons.
"""

from .commands import add_queue_commands, cmd_queue_list, cmd_queue_status
from .config import (
    DB_PATH,
    DEFAULT_WORKERS,
    HEARTBEAT_INTERVAL,
    HEAVY_COMMANDS,
    HEAVY_CONCURRENCY,
    MAX_COMPLETED_TASKS,
    MAX_CONCURRENT,
    MAX_FAILED_TASKS,
    MAX_WORKERS,
    QUEUE_DIR,
    RESULTS_DIR,
    TASK_TIMEOUT,
    TRANSCRIBE_CONCURRENCY,
    TaskStatus,
)
from .helpers import (
    benchmark_file_for,
    deserialize_result,
    get_result_artifacts,
    output_file_for,
    persist_benchmark,
    persist_result,
    results_dir_for,
    serialize_result,
    worker_log_file_for,
    write_file,
)
from .queue import TaskQueue, get_queue
from .store import TaskStore

__all__ = [
    # config
    "DB_PATH",
    "DEFAULT_WORKERS",
    "HEARTBEAT_INTERVAL",
    "HEAVY_COMMANDS",
    "HEAVY_CONCURRENCY",
    "MAX_COMPLETED_TASKS",
    "MAX_CONCURRENT",
    "MAX_FAILED_TASKS",
    "MAX_WORKERS",
    "QUEUE_DIR",
    "RESULTS_DIR",
    "TASK_TIMEOUT",
    "TRANSCRIBE_CONCURRENCY",
    "TaskStatus",
    # store
    "TaskStore",
    # queue
    "TaskQueue",
    "get_queue",
    # helpers
    "benchmark_file_for",
    "deserialize_result",
    "get_result_artifacts",
    "output_file_for",
    "persist_benchmark",
    "persist_result",
    "serialize_result",
    "worker_log_file_for",
    "write_file",
    "results_dir_for",
    # commands
    "add_queue_commands",
    "cmd_queue_list",
    "cmd_queue_status",
]
