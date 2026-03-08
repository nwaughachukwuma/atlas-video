"""Pure utility functions and shared helpers for CLI commands.

All heavy imports (``rich``, domain modules) are deferred inside function
bodies so that importing this module is essentially free.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rich.console import Console


# ── Logger ────────────────────────────────────────────────────────────────────


def get_logger():
    """Return the CLI-scoped logger (lazy to avoid import overhead on --help)."""
    from ..logger import get_logger as _get_logger

    return _get_logger("atlas:cli")


# ── Short helpers ─────────────────────────────────────────────────────────────


def short_name(full: str) -> str:
    """Strip module prefix from a qualified name.

    ``'atlas.utils.MediaFileManager._clip_media_async'`` → ``'_clip_media_async'``
    """
    v = full.rsplit(".", 1)
    return v[1] if len(v) > 1 else v[0]


def err(msg: str):
    """Print a red error message and exit with code 2 (client/validation error)."""
    from . import get_console

    get_console().print(f"[red]Error: {msg}[/red]")
    sys.exit(2)


def format_elapsed(seconds: float) -> str:
    """Return a human-readable duration string.

    Examples: ``0.91s`` → ``'0.91s'``  |  ``90.4s`` → ``'1m 30s'``  |  ``3661s`` → ``'1h 1m 1s'``
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {secs}s"


# ── Validation ────────────────────────────────────────────────────────────────


def validate_api_keys(require_gemini: bool = True, require_groq: bool = False) -> None:
    """Exit with a helpful message if required API keys are missing."""
    if require_gemini and not os.environ.get("GEMINI_API_KEY"):
        err("GEMINI_API_KEY environment variable is required.\nSet it with: export GEMINI_API_KEY=your-api-key")
    if require_groq and not os.environ.get("GROQ_API_KEY"):
        err(
            "GROQ_API_KEY environment variable is required for transcription.\n"
            "Set it with: export GROQ_API_KEY=your-api-key"
        )


def parse_duration(duration_str: str) -> int:
    """Parse duration string to seconds: ``'15s'`` → 15, ``'1m30s'`` → 90, ``'1h'`` → 3600."""
    s = duration_str.strip().lower()
    try:
        return int(s)
    except ValueError:
        pass
    total, current, parsed_any = 0, "", False
    for ch in s:
        if ch.isdigit():
            current += ch
        elif ch == "h" and current:
            total += int(current) * 3600
            current = ""
            parsed_any = True
        elif ch == "m" and current:
            total += int(current) * 60
            current = ""
            parsed_any = True
        elif ch == "s" and current:
            total += int(current)
            current = ""
            parsed_any = True
    if current:
        total += int(current)
        parsed_any = True
    if not parsed_any and s:
        err(f"Invalid duration format: {duration_str!r} — use e.g. 15s, 1m, 1m30s")
    return total


def validate_video_path(video_path: str) -> Path:
    """Return a validated, absolute ``Path`` or exit with an error."""
    path = Path(video_path).resolve()
    if not path.exists():
        err(f"Video file not found: {video_path}")
    if not path.is_file():
        err(f"Not a file: {video_path}")
    return path


# ── Rich helpers (lazy) ──────────────────────────────────────────────────────


def make_progress():
    """Create a rich ``Progress`` instance for indeterminate tasks."""
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    from . import get_console

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=get_console(),
    )


def print_queued_info(
    console: "Console",
    task_id: str,
    command: str,
    *,
    output_path: Optional[str] = None,
    benchmark: bool = False,
) -> None:
    """Print standardised information about a queued task."""
    from ..task_queue import benchmark_file_for, output_file_for, worker_log_file_for

    console.print("\n[bold green]✓ Task queued[/bold green]")
    console.print(f"  [cyan]Task ID:[/cyan]    {task_id}")
    console.print(f"  [cyan]Command:[/cyan]    {command}")
    console.print(f"  [cyan]Output:[/cyan]     {output_file_for(task_id)}")
    if output_path:
        console.print(f"  [cyan]Also at:[/cyan]    {output_path}")
    if benchmark:
        console.print(f"  [cyan]Benchmark:[/cyan]  {benchmark_file_for(task_id)}")
    console.print(f"  [cyan]Worker log:[/cyan] {worker_log_file_for(task_id)}")
    console.print(f"\n  [dim]Track this task:[/dim]  atlas queue status --task-id {task_id}")
    console.print("  [dim]View all tasks:[/dim]   atlas queue list")
    console.print("  [dim]System notification will fire on completion/failure.[/dim]")
    console.print("  [dim]You can keep using Atlas for new tasks.[/dim]")


def print_saved_run_info(
    console: "Console",
    run_id: str,
    command: str,
    *,
    output_path: str,
    requested_output_path: Optional[str] = None,
    benchmark_path: Optional[str] = None,
) -> None:
    """Print standardised information for a direct run persisted to disk."""
    console.print("\n[bold green]✓ Result persisted[/bold green]")
    console.print(f"  [cyan]Run ID:[/cyan]     {run_id}")
    console.print(f"  [cyan]Command:[/cyan]    {command}")
    console.print(f"  [cyan]Output:[/cyan]     {output_path}")
    if requested_output_path:
        console.print(f"  [cyan]Also at:[/cyan]    {requested_output_path}")
    if benchmark_path:
        console.print(f"  [cyan]Benchmark:[/cyan]  {benchmark_path}")
    console.print(f"\n  [dim]Inspect this run:[/dim] atlas queue status --task-id {run_id}")
    console.print("  [dim]Browse saved runs:[/dim] atlas queue list")


def print_benchmark_summary() -> None:
    """Print benchmark timing table if --benchmark was requested (set by ``_state``)."""
    from . import _state, get_console

    if not _state.get("benchmark"):
        return

    from rich.table import Table

    from ..benchmark import registry

    stats = registry.all_stats()
    if not stats:
        return

    console = get_console()
    console.print("\n[bold yellow]⏱  Benchmark Summary[/bold yellow]")
    table = Table(show_header=True, header_style="bold cyan", show_lines=False)
    table.add_column("Function", style="cyan", ratio=1, no_wrap=True, min_width=20)
    table.add_column("Runs", justify="right", width=5, style="dim")
    table.add_column("Total", justify="right", width=8)
    table.add_column("Avg", justify="right", width=7)
    table.add_column("Min", justify="right", width=7)
    table.add_column("Max", justify="right", width=7)
    for s in stats:
        table.add_row(
            short_name(s.name),
            str(s.calls),
            f"{s.total_s:.2f}s",
            f"{s.avg_s:.2f}s",
            f"{s.min_s:.2f}s",
            f"{s.max_s:.2f}s",
        )
    console.print(table)
