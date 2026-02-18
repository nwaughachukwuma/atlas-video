"""
Atlas CLI — stdlib argparse, zero third-party import overhead at startup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from rich.console import Console

    from .utils import DescriptionAttr


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

VERSION = "0.1.0"
PROG_NAME = "atlas"


# ---------------------------------------------------------------------------
# Lazy singletons — nothing heavy is imported until a real command runs
# ---------------------------------------------------------------------------

_console: Optional["Console"] = None


def get_console() -> "Console":
    global _console
    if _console is None:
        from rich.console import Console

        _console = Console()
    return _console


def get_logger():
    from .logger import logger

    return logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short_name(full: str) -> str:
    """Strip module prefix from a qualified name.
    'atlas.utils.MediaFileManager._clip_media_async' → '_clip_media_async'
    """
    v = full.rsplit(".", 1)
    return v[1] if len(v) > 1 else v[0]


def _print_benchmark_summary() -> None:
    """Print benchmark timing table if --benchmark was requested (set by _state)."""
    if not _state.get("benchmark"):
        return
    from rich.table import Table

    from .benchmark import registry

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
            _short_name(s.name),
            str(s.calls),
            f"{s.total_s:.2f}s",
            f"{s.avg_s:.2f}s",
            f"{s.min_s:.2f}s",
            f"{s.max_s:.2f}s",
        )
    console.print(table)


def _err(msg: str) -> None:
    get_console().print(f"[red]Error: {msg}[/red]")
    sys.exit(1)


def validate_api_keys(require_gemini: bool = True, require_groq: bool = False) -> None:
    if require_gemini and not os.environ.get("GEMINI_API_KEY"):
        _err("GEMINI_API_KEY environment variable is required.\nSet it with: export GEMINI_API_KEY=your-api-key")
    if require_groq and not os.environ.get("GROQ_API_KEY"):
        _err(
            "GROQ_API_KEY environment variable is required for transcription.\nSet it with: export GROQ_API_KEY=your-api-key"
        )


def parse_duration(duration_str: str) -> int:
    """Parse duration string to seconds: '15s' → 15, '1m30s' → 90, '1h' → 3600."""
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
        _err(f"Invalid duration format: {duration_str!r} — use e.g. 15s, 1m, 1m30s")
    return total


def validate_video_path(video_path: str) -> Path:
    path = Path(video_path)
    if not path.exists():
        _err(f"Video file not found: {video_path}")
    if not path.is_file():
        _err(f"Not a file: {video_path}")
    return path


def _make_progress():
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=get_console(),
    )


# ---------------------------------------------------------------------------
# Module-level state (set by _run_main before dispatching to a sub-command)
# ---------------------------------------------------------------------------

_state: dict = {"benchmark": False}


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _cmd_extract(args: argparse.Namespace) -> None:
    """Extract multimodal insights, printing each segment in real-time as it completes."""
    import asyncio as _asyncio

    from .utils import DEFAULT_DESCRIPTION_ATTRS, TempPath
    from .video_processor import VideoDescription, VideoProcessor, VideoProcessorConfig

    console = get_console()
    # extract uses Gemini for all analysis attrs (including transcript within chunks).
    # Groq is only needed for the standalone `transcribe` command.
    validate_api_keys(require_gemini=True, require_groq=False)

    video_path = str(validate_video_path(args.video_path))
    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)
    fmt: str = args.format

    description_attrs: List[DescriptionAttr] = list(args.attrs) if args.attrs else DEFAULT_DESCRIPTION_ATTRS
    valid_attrs: set = set(DEFAULT_DESCRIPTION_ATTRS)
    for attr in description_attrs:
        if attr not in valid_attrs:
            _err(f"Invalid attribute: {attr!r} — valid: {', '.join(sorted(valid_attrs))}")

    if fmt not in ("json", "text"):
        _err("--format must be 'json' or 'text'")

    json_to_stdout = fmt == "json" and not getattr(args, "output", None)
    if json_to_stdout:
        from rich.console import Console

        console = Console(stderr=True)

    console.print(f"\n[bold blue]Processing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]\n")

    all_descriptions: List[VideoDescription] = []
    output_parts: list[dict] = []

    def _on_segment(desc: VideoDescription) -> None:
        """Called in real-time as each segment completes."""
        all_descriptions.append(desc)
        if fmt == "text":
            console.print(f"[bold cyan]Segment {desc.start:.1f}s – {desc.end:.1f}s[/bold cyan]")
            for analysis in desc.video_analysis:
                label = " ".join(analysis.attr.upper().split("_"))
                value = analysis.value
                preview = value[:200] + "…" if len(value) > 200 else value
                console.print(f"  [yellow]{label}:[/yellow] {preview}")
            console.print()
        else:
            output_parts.append(desc.model_dump())

    async def _run():
        config = VideoProcessorConfig(
            video_path=video_path,
            chunk_duration=chunk_sec,
            overlap=overlap_sec,
            description_attrs=description_attrs,
            include_summary=args.include_summary,
        )
        async with VideoProcessor(config) as processor:
            result = await processor.process_realtime(_on_segment)
        return result

    try:
        result = _asyncio.run(_run())

        if fmt == "json":
            full_output = {
                "video_path": video_path,
                "duration": result.duration,
                "video_descriptions": output_parts,
            }
            output_str = json.dumps(full_output, indent=2)
            if args.output:
                Path(args.output).write_text(output_str)
                console.print(f"[green]Results saved to:[/green] {args.output}")
            else:
                print(output_str)
        else:
            console.print(f"[bold green]Done.[/bold green] {len(all_descriptions)} segments extracted.")
            if args.output:
                full_output = {
                    "video_path": video_path,
                    "duration": result.duration,
                    "video_descriptions": [d.model_dump() for d in all_descriptions],
                }
                Path(args.output).write_text(json.dumps(full_output, indent=2))
                console.print(f"[green]Full results saved to:[/green] {args.output}")
    except Exception as e:
        console.print(f"[red]Error processing video: {e}[/red]")
        get_logger().exception("Error in extract command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


def _cmd_index(args: argparse.Namespace) -> None:
    from .utils import TempPath
    from .vector_store.video_index import index_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=True)

    video_path = str(validate_video_path(args.video_path))
    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)

    console.print(f"\n[bold blue]Indexing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]")

    async def _run():
        with _make_progress() as progress:
            task = progress.add_task("Processing and indexing video…", total=None)
            video_id, indexed_count, result = await index_video(
                video_path=video_path,
                chunk_duration=chunk_sec,
                overlap=overlap_sec,
                store_path=args.store_path,
            )
            progress.update(task, completed=True)
        return video_id, indexed_count, result

    try:
        video_id, indexed_count, result = asyncio.run(_run())
        console.print("\n[bold green]Indexing complete![/bold green]")
        console.print(f"  [cyan]Video ID:[/cyan]          {video_id}")
        console.print(f"  Video:              {video_path}")
        console.print(f"  Duration:           {result.duration:.2f}s")
        console.print(f"  Segments processed: {len(result.video_descriptions)}")
        console.print(f"  Documents indexed:  {indexed_count}")
        console.print(f"  Index location:     {args.store_path or '~/.atlas/index'}")
        console.print(
            f"\n[dim]Use[/dim] [bold]atlas search --video-id {video_id} '...'[/bold] [dim]to query this video.[/dim]"
        )
    except Exception as e:
        console.print(f"[red]Error indexing video: {e}[/red]")
        get_logger().exception("Error in index command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


def _cmd_search(args: argparse.Namespace) -> None:
    from rich.table import Table

    from .vector_store.video_index import search_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=False)

    try:
        results = asyncio.run(
            search_video(
                query=args.query,
                top_k=args.top_k,
                video_id=args.video_id,
                store_path=args.store_path,
            )
        )
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            console.print("Make sure you have indexed some videos first with 'atlas index'")
            return

        console.print(f"\n[bold green]Found {len(results)} results for:[/bold green] '{args.query}'\n")
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


def _cmd_transcribe(args: argparse.Namespace) -> None:
    """Transcribe a video, streaming output to the terminal in real-time."""
    from .utils import TempPath
    from .video_processor import extract_transcript_realtime

    console = get_console()
    fmt: str = args.format
    if fmt not in ("text", "vtt", "srt"):
        _err("--format must be 'text', 'vtt', or 'srt'")

    validate_api_keys(require_gemini=False, require_groq=True)
    video_path = str(validate_video_path(args.video_path))

    console.print(f"\n[bold blue]Transcribing:[/bold blue] {video_path}")
    console.print(f"[dim]Output format: {fmt}[/dim]\n")

    output_lines: list[str] = []
    spinner_active = [True]

    def _on_chunk(text: str) -> None:
        """Called in real-time as each transcript chunk arrives."""
        output_lines.append(text)
        if not args.output:
            print(text, end="", flush=True)

    async def _run():
        return await extract_transcript_realtime(video_path, format=fmt, on_chunk=_on_chunk)

    try:
        final_result = asyncio.run(_run())
        full_text = final_result or "".join(output_lines)

        if not full_text.strip():
            console.print("[yellow]No transcript content generated.[/yellow]")
            return

        if args.output:
            Path(args.output).write_text(full_text)
            console.print(f"\n[green]Transcript saved to:[/green] {args.output}")
        else:
            # Ensure a trailing newline after the streamed output
            print()
    except Exception as e:
        console.print(f"[red]Error transcribing: {e}[/red]")
        get_logger().exception("Error in transcribe command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


def _cmd_chat(args: argparse.Namespace) -> None:
    """Chat with an indexed video using semantic context and chat history."""
    from .chat_handler import chat_with_video

    console = get_console()
    validate_api_keys(require_gemini=True, require_groq=False)

    video_id: str = args.video_id
    query: str = args.query

    console.print(f"\n[bold blue]Chat:[/bold blue] video_id=[cyan]{video_id}[/cyan]")
    console.print(f"[bold]You:[/bold] {query}\n")

    async def _run():
        with _make_progress() as progress:
            task = progress.add_task("Thinking…", total=None)
            answer = await chat_with_video(
                video_id=video_id,
                query=query,
                store_path=args.store_path,
            )
            progress.update(task, completed=True)
        return answer

    try:
        answer = asyncio.run(_run())
        console.print(f"[bold green]Atlas:[/bold green] {answer}\n")
    except Exception as e:
        console.print(f"[red]Error in chat: {e}[/red]")
        get_logger().exception("Error in chat command")
        sys.exit(1)


def _cmd_list_videos(args: argparse.Namespace) -> None:
    """List all videos that have been indexed in the vector store."""
    from rich.table import Table

    from .vector_store.video_index import default_video_index

    console = get_console()
    vi = default_video_index(store_path=args.store_path)
    videos = vi.list_videos()

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
    console.print(
        "\n[dim]Use[/dim] [bold]atlas search --video-id <VIDEO_ID> '...'[/bold] [dim]to search a specific video.[/dim]"
    )


def _cmd_list_chat(args: argparse.Namespace) -> None:
    """List the chat history for a given video."""
    from rich.table import Table

    from .vector_store.video_chat import default_video_chat

    console = get_console()
    video_id: str = args.video_id
    vc = default_video_chat(store_path=args.store_path)
    history = vc.get_history(video_id, last_n=args.last_n)

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


def _cmd_stats(args: argparse.Namespace) -> None:
    from rich import markup
    from rich.table import Table

    from .vector_store.video_chat import default_video_chat
    from .vector_store.video_index import default_video_index

    console = get_console()
    store_path = getattr(args, "store_path", None)
    vi = default_video_index(store_path=store_path)
    vc = default_video_chat(store_path=store_path)

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


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    # Shared parent that injects --benchmark into every subcommand.
    _shared = argparse.ArgumentParser(add_help=False)
    _shared.add_argument(
        "--benchmark",
        action="store_true",
        default=False,
        help="Print a per-function timing breakdown after the command completes.",
    )

    parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description="Atlas — Multimodal insights engine for video understanding.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Requires GEMINI_API_KEY for video analysis and GROQ_API_KEY for transcription.\n\n"
            "Examples:\n"
            "  atlas transcribe video.mp4\n"
            "  atlas extract video.mp4 --chunk-duration=15s\n"
            "  atlas index video.mp4 --store-path ./my_index\n"
            "  atlas search 'people discussing AI'\n"
            "  atlas search 'people discussing AI' --video-id abc123\n"
            "  atlas chat abc123 'What is this video about?'\n"
            "  atlas list-videos\n"
            "  atlas list-chat abc123\n"
            "  atlas stats\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"atlas {VERSION}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # ------------------------------------------------------------------
    # extract
    # ------------------------------------------------------------------
    p_extract = sub.add_parser(
        "extract",
        help="Extract multimodal insights from a video.",
        description=(
            "Analyze video content and extract visual cues, interactions, contextual "
            "information, audio analysis, and transcripts. Results stream to the terminal "
            "in real-time as each segment is processed."
        ),
        epilog="Example:\n  atlas extract video.mp4 --chunk-duration=15s --overlap=1s",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_extract.add_argument("video_path", help="Path to the video file.")
    p_extract.add_argument(
        "--chunk-duration", "-c", default="15s", metavar="DUR", help="Duration of each chunk (default: 15s)."
    )
    p_extract.add_argument("--overlap", "-l", default="1s", metavar="DUR", help="Overlap between chunks (default: 1s).")
    p_extract.add_argument(
        "--attrs",
        "-a",
        action="append",
        metavar="ATTR",
        help="Attribute to extract; repeat for multiple (visual_cues, interactions, contextual_information, audio_analysis, transcript).",
    )
    p_extract.add_argument("--output", "-o", metavar="FILE", help="Output file path (JSON).")
    p_extract.add_argument(
        "--format", "-f", default="text", metavar="FMT", help="Output format: json or text (default: text)."
    )
    p_extract.add_argument(
        "--include-summary",
        action="store_true",
        default=True,
        dest="include_summary",
        help="Generate a summary for each segment (default: enabled).",
    )
    p_extract.add_argument(
        "--no-summary",
        action="store_false",
        dest="include_summary",
        help="Disable per-segment summary generation.",
    )
    p_extract.set_defaults(func=_cmd_extract)

    # ------------------------------------------------------------------
    # index
    # ------------------------------------------------------------------
    p_index = sub.add_parser(
        "index",
        help="Index a video for semantic search.",
        description=(
            "Process a video and store embeddings in a local vector store for fast "
            "semantic search. Prints the assigned video_id on completion."
        ),
        epilog="Example:\n  atlas index video.mp4 --chunk-duration=15s",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_index.add_argument("video_path", help="Path to the video file.")
    p_index.add_argument(
        "--chunk-duration", "-c", default="15s", metavar="DUR", help="Duration of each chunk (default: 15s)."
    )
    p_index.add_argument("--overlap", "-o", default="0s", metavar="DUR", help="Overlap between chunks (default: 0s).")
    p_index.add_argument("--store-path", "-s", default=None, metavar="DIR", help="Path to store the vector index.")
    p_index.add_argument(
        "--embedding-dim",
        "-e",
        type=int,
        default=768,
        metavar="N",
        help="Embedding dimension: 768 or 3072 (default: 768).",
    )
    p_index.set_defaults(func=_cmd_index)

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    p_search = sub.add_parser(
        "search",
        help="Search indexed videos semantically.",
        description="Run a natural-language query against previously indexed videos.",
        epilog=(
            "Examples:\n  atlas search 'people discussing AI'\n  atlas search 'people discussing AI' --video-id abc123"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_search.add_argument("query", help="Natural-language search query.")
    p_search.add_argument(
        "--top-k", "-k", type=int, default=10, metavar="N", help="Number of results to return (default: 10)."
    )
    p_search.add_argument(
        "--video-id",
        "-v",
        default=None,
        metavar="ID",
        dest="video_id",
        help="Filter results to a specific video ID (returned by 'atlas index').",
    )
    p_search.add_argument("--store-path", "-s", default=None, metavar="DIR", help="Path to the vector index.")
    p_search.set_defaults(func=_cmd_search)

    # ------------------------------------------------------------------
    # transcribe
    # ------------------------------------------------------------------
    p_transcribe = sub.add_parser(
        "transcribe",
        help="Extract transcript from a video or audio file.",
        description=(
            "Transcribe a video or audio file using Groq Whisper. Output streams to the terminal in real-time."
        ),
        epilog="Example:\n  atlas transcribe video.mp4 --format=srt --output=transcript.srt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_transcribe.add_argument("video_path", help="Path to the video or audio file.")
    p_transcribe.add_argument(
        "--format", "-f", default="text", metavar="FMT", help="Output format: text, vtt, or srt (default: text)."
    )
    p_transcribe.add_argument("--output", "-o", default=None, metavar="FILE", help="Output file path.")
    p_transcribe.set_defaults(func=_cmd_transcribe)

    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------
    p_chat = sub.add_parser(
        "chat",
        help="Chat with an indexed video using AI.",
        description=(
            "Ask questions about a previously indexed video. Context is sourced from "
            "the vector store (top-k multimodal insights) and prior conversation history."
        ),
        epilog="Example:\n  atlas chat abc123 'What tools are used in this video?'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_chat.add_argument("video_id", help="Video ID returned by 'atlas index'.")
    p_chat.add_argument("query", help="Your question about the video.")
    p_chat.add_argument("--store-path", "-s", default=None, metavar="DIR", help="Path to the vector index.")
    p_chat.set_defaults(func=_cmd_chat)

    # ------------------------------------------------------------------
    # list-videos
    # ------------------------------------------------------------------
    p_list_videos = sub.add_parser(
        "list-videos",
        help="List all indexed videos.",
        description="Display all videos that have been indexed in the local vector store.",
        epilog="Example:\n  atlas list-videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_list_videos.add_argument("--store-path", "-s", default=None, metavar="DIR", help="Path to the vector index.")
    p_list_videos.set_defaults(func=_cmd_list_videos)

    # ------------------------------------------------------------------
    # list-chat
    # ------------------------------------------------------------------
    p_list_chat = sub.add_parser(
        "list-chat",
        help="List chat history for a video.",
        description="Display the stored chat history for a given video ID.",
        epilog="Example:\n  atlas list-chat abc123",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_list_chat.add_argument("video_id", help="Video ID to retrieve chat history for.")
    p_list_chat.add_argument(
        "--last-n",
        "-n",
        type=int,
        default=20,
        metavar="N",
        help="Maximum number of messages to show (default: 20).",
    )
    p_list_chat.add_argument("--store-path", "-s", default=None, metavar="DIR", help="Path to the vector index.")
    p_list_chat.set_defaults(func=_cmd_list_chat)

    # ------------------------------------------------------------------
    # stats
    # ------------------------------------------------------------------
    p_stats = sub.add_parser(
        "stats",
        help="Show statistics about the local vector store.",
        description="Display key metrics about the local Atlas vector index.",
        epilog="Example:\n  atlas stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_stats.add_argument("--store-path", "-s", default=None, metavar="DIR", help="Path to the vector index.")
    p_stats.set_defaults(func=_cmd_stats)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _format_elapsed(seconds: float) -> str:
    """Return a human-readable duration string.

    Examples: 0.91s → '0.91s'  |  90.4s → '1m 30s'  |  3661s → '1h 1m 1s'
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


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Store global flags before dispatching
    _state["benchmark"] = args.benchmark

    # Load .env only when a real command is about to run (never on --help/--version
    # since those exit during parse_args before we reach here).
    from time import perf_counter

    from dotenv import load_dotenv

    load_dotenv()

    t0 = perf_counter()
    try:
        args.func(args)
    except Exception as e:
        get_console().print(f"[red]Error while executing: {e}[/red]")
        sys.exit(1)
    finally:
        _print_benchmark_summary()
        elapsed = perf_counter() - t0
        get_console().print(f"\n[dim]Finished in {_format_elapsed(elapsed)}[/dim]")


if __name__ == "__main__":
    main()
