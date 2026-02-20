"""
Atlas CLI — stdlib argparse, zero third-party import overhead at startup.

This package splits the CLI into focused modules while keeping every heavy
import deferred until a real command runs.  The public surface (``main``,
``get_console``, individual ``_cmd_*`` handlers, helpers …) is re-exported
here so that existing call-sites and tests continue to work via
``from atlas.cli import …``.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rich.console import Console

# ── version ───────────────────────────────────────────────────────────────────

VERSION = "0.1.0"
PROG_NAME = "atlas"

# ── Lazy singletons — nothing heavy is imported until a real command runs ─────

_console: Optional["Console"] = None


def get_console() -> "Console":
    """Return (or create) the process-wide rich ``Console`` instance."""
    global _console
    if _console is None:
        from rich.console import Console

        _console = Console()
    return _console


def get_logger():
    """Return the CLI logger (lazy import to avoid overhead on --help)."""
    from .helpers import get_logger as _gl

    return _gl()


# ── Module-level state (set by main() before dispatching to a sub-command) ────

_state: dict = {"benchmark": False}


# ── Re-exports ────────────────────────────────────────────────────────────────
# Every symbol previously importable from ``atlas.cli`` is re-exported here so
# that existing test code and user scripts keep working unchanged.

from .cmd_explore import (  # noqa: E402
    _cmd_chat as _cmd_chat,
)
from .cmd_explore import (
    _cmd_get_data as _cmd_get_data,
)
from .cmd_explore import (
    _cmd_list_chat as _cmd_list_chat,
)
from .cmd_explore import (
    _cmd_list_videos as _cmd_list_videos,
)
from .cmd_explore import (
    _cmd_search as _cmd_search,
)
from .cmd_explore import (
    _cmd_stats as _cmd_stats,
)
from .cmd_media import (  # noqa: E402
    _cmd_extract as _cmd_extract,
)
from .cmd_media import (
    _cmd_index as _cmd_index,
)
from .cmd_media import (
    _cmd_transcribe as _cmd_transcribe,
)
from .helpers import (  # noqa: E402
    _err as _err,
)
from .helpers import (
    _format_elapsed as _format_elapsed,
)
from .helpers import (
    _make_progress as _make_progress,
)
from .helpers import (
    _print_benchmark_summary as _print_benchmark_summary,
)
from .helpers import (
    _print_queued_info as _print_queued_info,
)
from .helpers import (
    _short_name as _short_name,
)
from .helpers import (
    parse_duration as parse_duration,
)
from .helpers import (
    validate_api_keys as validate_api_keys,
)
from .helpers import (
    validate_video_path as validate_video_path,
)
from .parser import _build_parser as _build_parser  # noqa: E402
from .tasks import (  # noqa: E402
    _run_extract as _run_extract,
)
from .tasks import (
    _run_index as _run_index,
)
from .tasks import (
    _run_transcribe as _run_transcribe,
)

# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Parse argv and dispatch to the appropriate command handler."""
    parser = _build_parser()
    args = parser.parse_args()

    # Store global flags before dispatching.
    _state["benchmark"] = getattr(args, "benchmark", False)

    # Load .env only when a real command is about to run (never on --help/--version
    # since those exit during parse_args before we reach here).
    from time import perf_counter

    from dotenv import load_dotenv

    load_dotenv()

    is_queue_cmd = getattr(args, "command", None) == "queue"
    is_queuing = False
    if getattr(args, "command", None) in ("extract", "transcribe", "index"):
        is_queuing = not getattr(args, "no_queue", False)

    t0 = perf_counter()
    try:
        args.func(args)
    except Exception as e:
        get_console().print(f"[red]Error while executing: {e}[/red]")
        sys.exit(1)
    finally:
        _print_benchmark_summary()
        # Suppress "Finished in Xs" for queue commands and queued tasks.
        if not is_queue_cmd and not is_queuing:
            elapsed = perf_counter() - t0
            get_console().print(f"\n[dim]Finished in {_format_elapsed(elapsed)}[/dim]")


if __name__ == "__main__":
    main()
