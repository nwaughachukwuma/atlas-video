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


def output_file_for(task_id: str) -> Path:
    """Return the canonical stored output file for a given task/run ID."""
    return results_dir_for(task_id) / "output.json"


def benchmark_file_for(task_id: str) -> Path:
    """Return the canonical stored benchmark file for a given task/run ID."""
    return results_dir_for(task_id) / "benchmark.txt"


def worker_log_file_for(task_id: str) -> Path:
    """Return the worker log file path for a queued task."""
    return results_dir_for(task_id) / "worker.log"


def persist_result(
    task_id: str,
    result: Any,
    *,
    output_path: str | None = None,
    user_content: str | None = None,
) -> tuple[str, str]:
    """Persist a run result to the canonical results directory and optional user path."""
    content = serialize_result(result)
    result_path = output_file_for(task_id)
    write_file(result_path, content)
    if output_path:
        write_file(Path(output_path), user_content if user_content is not None else content)
    return content, str(result_path)


def render_benchmark_text(total_s: float | None = None) -> str | None:
    """Render the benchmark summary table as text, if any benchmark stats exist."""
    try:
        from ..benchmark import registry

        stats = registry.all_stats()
        if not stats:
            return None

        headers = ("Function", "Calls", "Total (s)", "Avg (s)", "Min (s)", "Max (s)")
        rows = [
            (
                s.name,
                str(s.calls),
                f"{s.total_s:.3f}",
                f"{s.avg_s:.3f}",
                f"{s.min_s:.3f}",
                f"{s.max_s:.3f}",
            )
            for s in stats
        ]

        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        def _fmt_row(cells: tuple[str, ...]) -> str:
            return "| " + " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

        sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
        lines = [
            "Benchmark Summary",
            sep,
            _fmt_row(headers),
            sep,
            *[_fmt_row(r) for r in rows],
            sep,
        ]
        if total_s is not None:
            lines.append(f"\nTotal runtime: {total_s:.2f}s")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Failed to render benchmark summary: %s", exc)
        return None


def persist_benchmark(task_id: str, total_s: float | None = None) -> tuple[str | None, str | None]:
    """Persist benchmark output for a task/run and return the text/path when available."""
    content = render_benchmark_text(total_s=total_s)
    if content is None:
        return None, None
    path = benchmark_file_for(task_id)
    write_file(path, content)
    return content, str(path)


def deserialize_result(content: str | None) -> Any:
    """Parse stored output content back into JSON when possible."""
    if content is None:
        return None
    stripped = content.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return content


def get_result_artifacts(task: dict[str, Any]) -> dict[str, Any]:
    """Resolve persisted result metadata for a task/run, including backwards-compatible file fallbacks."""
    task_id = str(task["id"])
    output_path = Path(task.get("result_path") or output_file_for(task_id))
    benchmark_path = Path(task.get("benchmark_path") or benchmark_file_for(task_id))
    result_text = task.get("result_text")
    benchmark_text = task.get("benchmark_text")

    if result_text is None and output_path.exists():
        result_text = output_path.read_text()
    if benchmark_text is None and benchmark_path.exists():
        benchmark_text = benchmark_path.read_text()

    return {
        "result_path": str(output_path) if output_path.exists() or result_text is not None else None,
        "benchmark_path": str(benchmark_path) if benchmark_path.exists() or benchmark_text is not None else None,
        "result_text": result_text,
        "benchmark_text": benchmark_text,
    }
