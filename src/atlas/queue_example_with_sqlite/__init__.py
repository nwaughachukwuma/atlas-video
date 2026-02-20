"""
taskqueue — Simple, disk-backed, process-pool task queue for Python CLI apps.
No Redis. No broker. No long-lived daemon. Just SQLite + multiprocessing.
"""

from .queue import TaskQueue
from .store import Status

__all__ = ["TaskQueue", "Status"]
