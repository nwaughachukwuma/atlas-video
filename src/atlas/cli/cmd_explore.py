"""Command handlers for search, chat, list-videos, list-chat, and stats."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .helpers import make_progress, validate_api_keys

# ── search ────────────────────────────────────────────────────────────────────


def cmd_search(args: argparse.Namespace) -> None:
    """Run a semantic search against previously indexed videos."""
    import json

    from . import get_console, get_logger
    from ..vector_store.video_index import search_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=False)

    pos = args.search_args
    if len(pos) >= 2:
        video_id, query = pos[0], " ".join(pos[1:])
    elif len(pos) == 1:
        video_id, query = None, pos[0]
    else:
        console.print("[red]Error: At least a search query is required.[/red]")
        sys.exit(1)

    try:
        results = asyncio.run(search_video(query, args.top_k, video_id))
        output = {
            "query": query,
            "video_id": video_id,
            "count": len(results),
            "results": [r.model_dump() for r in results],
        }
        print(json.dumps(output, indent=2))
    except Exception as e:
        console.print(f"[red]Error searching: {e}[/red]")
        get_logger().exception("Error in search command")
        sys.exit(1)


# ── chat ──────────────────────────────────────────────────────────────────────


def cmd_chat(args: argparse.Namespace) -> None:
    """Chat with an indexed video using semantic context and chat history."""
    from . import get_console, get_logger
    from ..chat_handler import chat_with_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=False)

    video_id: str = args.video_id
    query: str = args.query

    console.print(f"\n[bold blue]Chat:[/bold blue] video_id=[cyan]{video_id}[/cyan]")
    console.print(f"[bold]You:[/bold] {query}\n")

    async def _run() -> None:
        # Show a lightweight indicator while context retrieval runs (before first
        # token arrives).  As soon as the model starts streaming we clear it and
        # print the response prefix.
        sys.stdout.write("Thinking…")
        sys.stdout.flush()

        first_chunk = True
        async for chunk in chat_with_video(video_id, query):
            if first_chunk:
                # Overwrite the "Thinking…" line with the Atlas response prefix.
                sys.stdout.write("\r" + " " * 12 + "\r")
                console.print("[bold green]Atlas:[/bold green] ", end="")
                first_chunk = False
            sys.stdout.write(chunk)
            sys.stdout.flush()

        if first_chunk:
            # No chunks were yielded — something went wrong.
            sys.stdout.write("\r" + " " * 12 + "\r")
            console.print("[yellow]No response received.[/yellow]")
        else:
            sys.stdout.write("\n\n")
            sys.stdout.flush()

    try:
        asyncio.run(_run())
    except Exception as e:
        console.print(f"\n[red]Error in chat: {e}[/red]")
        get_logger().exception("Error in chat command")
        sys.exit(1)


# ── list-videos ───────────────────────────────────────────────────────────────


def cmd_list_videos(args: argparse.Namespace) -> None:
    """List all videos that have been indexed in the vector store."""
    import json

    from ..vector_store.video_index import default_video_index

    vi = default_video_index()
    videos = vi.list_videos()
    print(
        json.dumps(
            {
                "count": len(videos),
                "videos": [{"video_id": v.video_id, "indexed_at": v.indexed_at} for v in videos],
            },
            indent=2,
        )
    )


# ── list-chat ─────────────────────────────────────────────────────────────────


def cmd_list_chat(args: argparse.Namespace) -> None:
    """List the chat history for a given video."""
    import json

    from . import get_console
    from ..vector_store.video_chat import default_video_chat

    console = get_console()
    video_id: str = args.video_id
    with make_progress() as progress:
        task = progress.add_task("Loading chat history...", total=None)
        vc = default_video_chat()
        history = vc.get_history(video_id, last_n=args.last_n)
        progress.update(task, completed=True)

    output = {
        "video_id": video_id,
        "count": len(history),
        "messages": history,
    }
    print(json.dumps(output, indent=2))


# ── stats ─────────────────────────────────────────────────────────────────────


def cmd_stats(args: argparse.Namespace) -> None:
    """Show statistics about the local vector store."""
    import json

    from . import get_console
    from ..vector_store.video_chat import default_video_chat
    from ..vector_store.video_index import default_video_index

    console = get_console()
    with make_progress() as progress:
        task = progress.add_task("Loading stats...", total=None)
        vi = default_video_index()
        vc = default_video_chat()
        progress.update(task, completed=True)

    output = {
        "video_col_path": str(vi.col_path),
        "video_index_stats": str(vi.stats),
        "chat_col_path": str(vc.col_path),
        "chat_index_stats": str(vc.stats),
        "videos_indexed": len(vi.list_videos()),
    }
    print(json.dumps(output, indent=2))


# ── get-data ───────────────────────────────────────────────────────────────────────


def cmd_get_data(args: argparse.Namespace) -> None:
    """Retrieve all indexed data for a video in extract-command shape."""
    import json
    from pathlib import Path

    from . import get_console
    from ..vector_store.video_index import default_video_index

    console = get_console()
    video_id: str = args.video_id
    output_path: str | None = getattr(args, "output", None)

    with make_progress() as progress:
        task = progress.add_task("Fetching video data…", total=None)
        vi = default_video_index()
        data = vi.get_video_data(video_id)
        progress.update(task, completed=True)

    if not data:
        console.print(f"[yellow]No data found for video_id=[/yellow][cyan]{video_id}[/cyan]")
        console.print("Make sure the video has been indexed with: [bold]atlas index video.mp4[/bold]")
        return

    output_str = json.dumps(data, indent=2)
    if output_path:
        Path(output_path).write_text(output_str)
        console.print(f"[green]Data saved to:[/green] {output_path}")
    else:
        print(output_str)
