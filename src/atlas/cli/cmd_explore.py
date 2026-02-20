"""Command handlers for search, chat, list-videos, list-chat, and stats."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .helpers import _make_progress, validate_api_keys

# ── search ────────────────────────────────────────────────────────────────────


def _cmd_search(args: argparse.Namespace) -> None:
    """Run a semantic search against previously indexed videos."""
    from rich.table import Table

    from . import get_console, get_logger
    from ..vector_store.video_index import search_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=False)

    pos = args.search_args
    if len(pos) >= 2:
        video_id, query = pos[0], " ".join(pos[1:])
    else:
        video_id, query = None, pos[0]

    try:
        results = asyncio.run(search_video(query, args.top_k, video_id))
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            console.print("Make sure you have indexed some videos first with 'atlas index'")
            return

        console.print(f"\n[bold green]Found {len(results)} results for:[/bold green] '{query}'\n")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Video ID", width=20)
        table.add_column("Time", width=15)
        table.add_column("Content", width=55)
        for i, result in enumerate(results, 1):
            time_str = f"{result.start:.1f}s – {result.end:.1f}s"
            content = result.content[:52] + "…" if len(result.content) > 55 else result.content
            vid_id = result.video_id
            if len(vid_id) > 20:
                vid_id = vid_id[:17] + "…"
            table.add_row(str(i), f"{result.score:.3f}", vid_id, time_str, content)
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error searching: {e}[/red]")
        get_logger().exception("Error in search command")
        sys.exit(1)


# ── chat ──────────────────────────────────────────────────────────────────────


def _cmd_chat(args: argparse.Namespace) -> None:
    """Chat with an indexed video using semantic context and chat history."""
    from . import get_console, get_logger
    from ..chat_handler import chat_with_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=False)

    video_id: str = args.video_id
    query: str = args.query

    console.print(f"\n[bold blue]Chat:[/bold blue] video_id=[cyan]{video_id}[/cyan]")
    console.print(f"[bold]You:[/bold] {query}\n")

    async def _run():
        with _make_progress() as progress:
            task = progress.add_task("Thinking…", total=None)
            answer = await chat_with_video(video_id=video_id, query=query)
            progress.update(task, completed=True)
        return answer

    try:
        answer = asyncio.run(_run())
        console.print(f"[bold green]Atlas:[/bold green] {answer}\n")
    except Exception as e:
        console.print(f"[red]Error in chat: {e}[/red]")
        get_logger().exception("Error in chat command")
        sys.exit(1)


# ── list-videos ───────────────────────────────────────────────────────────────


def _cmd_list_videos(args: argparse.Namespace) -> None:
    """List all videos that have been indexed in the vector store."""
    from rich.table import Table

    from . import get_console
    from ..vector_store.video_index import default_video_index

    console = get_console()
    with _make_progress() as progress:
        task = progress.add_task("Loading videos...", total=None)
        vi = default_video_index()
        videos = vi.list_videos()
        progress.update(task, completed=True)

    if not videos:
        console.print("[yellow]No videos indexed yet.[/yellow]")
        console.print("Index a video first with: [bold]atlas index video.mp4[/bold]")
        return

    console.print(f"\n[bold blue]Indexed Videos[/bold blue] ({len(videos)} total)\n")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Video ID", style="cyan", width=36)
    table.add_column("Indexed At", width=28)
    for i, entry in enumerate(videos, 1):
        table.add_row(str(i), entry.video_id, entry.indexed_at)
    console.print(table)
    console.print("\n[dim]Use[/dim] [bold]atlas search <VIDEO_ID> '...'[/bold] [dim]to search a specific video.[/dim]")
    console.print(
        "\n[dim]Use[/dim] [bold]atlas get-video <VIDEO_ID>[/bold] [dim]to retrieve all indexed data for a video.[/dim]"
    )
    console.print("\n[dim]Use[/dim] [bold]atlas chat <VIDEO_ID> '<query>'[/bold] [dim]to chat with your video.[/dim]")


# ── list-chat ─────────────────────────────────────────────────────────────────


def _cmd_list_chat(args: argparse.Namespace) -> None:
    """List the chat history for a given video."""
    from rich.table import Table

    from . import get_console
    from ..vector_store.video_chat import default_video_chat

    console = get_console()
    video_id: str = args.video_id
    with _make_progress() as progress:
        task = progress.add_task("Loading chat history...", total=None)
        vc = default_video_chat()
        history = vc.get_history(video_id, last_n=args.last_n)
        progress.update(task, completed=True)

    if not history:
        console.print(f"[yellow]No chat history for video_id=[/yellow][cyan]{video_id}[/cyan]")
        console.print(f"Start a chat with: [bold]atlas chat {video_id} 'your question'[/bold]")
        return

    console.print(f"\n[bold blue]Chat History[/bold blue] for [cyan]{video_id}[/cyan] ({len(history)} messages)\n")
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Role", width=12)
    table.add_column("Message", ratio=1)
    table.add_column("Timestamp", width=22)
    for i, msg in enumerate(history, 1):
        role = msg.get("role", "?")
        color = "green" if role == "assistant" else "yellow"
        table.add_row(
            str(i),
            f"[{color}]{role}[/{color}]",
            msg.get("content", ""),
            msg.get("timestamp", ""),
        )
    console.print(table)


# ── stats ─────────────────────────────────────────────────────────────────────


def _cmd_stats(args: argparse.Namespace) -> None:
    """Show statistics about the local vector store."""
    from rich import markup
    from rich.table import Table

    from . import get_console
    from ..vector_store.video_chat import default_video_chat
    from ..vector_store.video_index import default_video_index

    console = get_console()
    with _make_progress() as progress:
        task = progress.add_task("Loading stats...", total=None)
        vi = default_video_index()
        vc = default_video_chat()
        progress.update(task, completed=True)

    stats_data = {
        "video_col_path": str(vi.col_path),
        "video_index_stats": str(vi.stats),
        "chat_col_path": str(vc.col_path),
        "chat_index_stats": str(vc.stats),
        "videos_indexed": str(len(vi.list_videos())),
    }

    console.print("\n[bold blue]Atlas Vector Store Statistics[/bold blue]\n")
    table = Table(show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    for key, value in stats_data.items():
        table.add_row(key, markup.escape(value))
    console.print(table)


# ── get-data ───────────────────────────────────────────────────────────────────────


def _cmd_get_data(args: argparse.Namespace) -> None:
    """Retrieve all indexed data for a video in extract-command shape."""
    import json
    from pathlib import Path

    from . import get_console
    from ..vector_store.video_index import default_video_index

    console = get_console()
    video_id: str = args.video_id
    output_path: str | None = getattr(args, "output", None)

    with _make_progress() as progress:
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
