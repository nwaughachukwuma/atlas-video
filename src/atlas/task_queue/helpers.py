"""
Shared file and serialisation helpers for the task queue
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import RESULTS_DIR
from ..logger import get_logger

logger = get_logger("atlas:queue")


def write_file(path: Path, content: str) -> None:
    """Write *content* to *path*, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    except Exception as exc:
        logger.warning("Failed to write %s: %s", path, exc)


def serialize_result(result: Any) -> str:
    """Convert a task result to a string suitable for writing to disk."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), indent=2, default=str)
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, default=str)
    return str(result)


def results_dir_for(task_id: str) -> Path:
    """Return the results directory for a given task ID."""
    return RESULTS_DIR / task_id
