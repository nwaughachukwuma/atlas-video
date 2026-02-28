"""Command handlers for extract, transcribe, and index (the "heavy" video commands)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from .helpers import (
    err,
    make_progress,
    parse_duration,
    print_queued_info,
    validate_api_keys,
    validate_video_path,
)

if TYPE_CHECKING:
    from ..utils import DescriptionAttr


# ── extract ───────────────────────────────────────────────────────────────────


def cmd_extract(args: argparse.Namespace) -> None:
    """Extract multimodal insights, optionally queuing the task."""
    from . import get_console, get_logger

    console = get_console()
    use_queue = not getattr(args, "no_queue", False)
    no_streaming = getattr(args, "no_streaming", False)
    benchmark = getattr(args, "benchmark", False)
    fmt: str = args.format
    output_path: Optional[str] = getattr(args, "output", None)

    if fmt not in ("json", "text"):
        err("--format must be 'json' or 'text'")

    validate_api_keys(require_gemini=True, require_groq=False)
    video_path = validate_video_path(args.video_path)

    if use_queue:
        from ..task_queue import get_queue

        queue = get_queue()
        args_copy = argparse.Namespace(**vars(args))
        args_copy._video_path_resolved = str(video_path)

        task_id = queue.submit(
            args_copy,
            command="extract",
            label=f"extract {video_path.name}",
            output_path=output_path,
            benchmark=benchmark,
        )
        print_queued_info(
            console,
            task_id,
            "extract",
            output_path=output_path,
            benchmark=benchmark,
        )
        return

    # ── Direct execution (no queue) ───────────────────────────────────
    from ..utils import DEFAULT_DESCRIPTION_ATTRS, TempPath
    from ..video_processor import VideoDescription, VideoProcessor, VideoProcessorConfig

    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)

    if args.attrs:
        for attr in list(args.attrs):
            if attr not in DEFAULT_DESCRIPTION_ATTRS:
                err(f"Invalid attribute: {attr!r} — valid: {', '.join(sorted(DEFAULT_DESCRIPTION_ATTRS))}")
        description_attrs: List[DescriptionAttr] = list(args.attrs)
    else:
        description_attrs = DEFAULT_DESCRIPTION_ATTRS

    # --no-queue always outputs JSON; redirect console to stderr to keep stdout clean
    from rich.console import Console

    console = Console(stderr=True)

    console.print(f"\n[bold blue]Processing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]\n")

    def _on_segment(desc: VideoDescription) -> None:
        if not no_streaming:
            segment_str = desc.model_dump_json(indent=2)
            print("STREAMED SEGMENT: ", segment_str)

    try:

        async def _run():
            config = VideoProcessorConfig(
                video_path=str(video_path),
                chunk_duration=chunk_sec,
                overlap=overlap_sec,
                description_attrs=description_attrs,
                include_summary=args.include_summary,
            )
            async with VideoProcessor(config) as processor:
                return await processor.process(_on_segment)

        result = asyncio.run(_run())
        assert result is not None, "VideoProcessor.process() returned None"

        output_str = result.model_dump_json(indent=2)
        if output_path:
            Path(output_path).write_text(output_str)
            console.print(f"[green]Results saved to:[/green] {output_path}")
        else:
            print(output_str)
    except Exception as e:
        console.print(f"[red]Error processing video: {e}[/red]")
        get_logger().exception("Error in extract command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


# ── transcribe ────────────────────────────────────────────────────────────────


def cmd_transcribe(args: argparse.Namespace) -> None:
    """Transcribe a video, optionally queuing the task."""
    from . import get_console, get_logger
    from ..utils import TempPath

    console = get_console()
    fmt = args.format
    use_queue = not getattr(args, "no_queue", False)
    no_streaming = getattr(args, "no_streaming", False)
    benchmark = getattr(args, "benchmark", False)
    output_path: Optional[str] = getattr(args, "output", None)

    if fmt not in ("text", "vtt", "srt"):
        err("--format must be 'text', 'vtt', or 'srt'")

    validate_api_keys(require_gemini=False, require_groq=True)
    video_path = validate_video_path(args.video_path)

    if use_queue:
        from ..task_queue import get_queue

        queue = get_queue()
        args_copy = argparse.Namespace(**vars(args))
        args_copy._video_path_resolved = str(video_path)

        task_id = queue.submit(
            args_copy,
            command="transcribe",
            label=f"transcribe {video_path.name}",
            output_path=output_path,
            benchmark=benchmark,
        )
        print_queued_info(
            console,
            task_id,
            "transcribe",
            output_path=output_path,
            benchmark=benchmark,
        )
        return

    # ── Direct execution (no queue) ───────────────────────────────────
    from rich.console import Console

    from ..transcript import get_video_transcript

    console = Console(stderr=True)

    console.print(f"\n[bold blue]Transcribing:[/bold blue] {video_path}")
    console.print(f"[dim]Output format: {fmt}[/dim]\n")

    def _on_chunk(text: str) -> None:
        if not no_streaming:
            print("STREAMED CHUNK:", text)

    async def _run():
        return await get_video_transcript(
            str(video_path),
            format=fmt,
            on_chunk=_on_chunk,
        )

    try:
        with make_progress() as progress:
            task = progress.add_task("Transcribing...", total=None)
            full_text = asyncio.run(_run())
            progress.update(task, completed=True)

        if not full_text.strip():
            console.print("[yellow]No transcript content generated.[/yellow]")
            return

        if output_path:
            Path(output_path).write_text(full_text)
            console.print(f"\n[green]Transcript saved to:[/green] {output_path}")
        else:
            result = {"transcript": full_text, "format": fmt}
            print(json.dumps(result, indent=2))
    except Exception as e:
        console.print(f"[red]Error transcribing: {e}[/red]")
        get_logger().exception("Error in transcribe command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


# ── index ─────────────────────────────────────────────────────────────────────


def cmd_index(args: argparse.Namespace) -> None:
    """Index a video for semantic search, optionally queuing the task."""
    from . import get_console, get_logger
    from ..utils import TempPath

    console = get_console()
    use_queue = not getattr(args, "no_queue", False)
    no_streaming = getattr(args, "no_streaming", False)
    benchmark = getattr(args, "benchmark", False)

    validate_api_keys(require_gemini=True, require_groq=True)
    video_path = validate_video_path(args.video_path)
    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)

    if use_queue:
        from ..task_queue import get_queue

        queue = get_queue()
        args_copy = argparse.Namespace(**vars(args))
        args_copy._video_path_resolved = str(video_path)

        task_id = queue.submit(
            args_copy,
            command="index",
            label=f"index {video_path.name}",
            benchmark=benchmark,
        )
        print_queued_info(console, task_id, "index", benchmark=benchmark)
        return

    # ── Direct execution (no queue) ───────────────────────────────────
    from rich.console import Console

    from ..utils import DEFAULT_DESCRIPTION_ATTRS
    from ..vector_store.video_index import index_video
    from ..video_processor import VideoDescription

    console = Console(stderr=True)

    console.print(f"\n[bold blue]Indexing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]")

    def _on_segment(desc: VideoDescription) -> None:
        if not no_streaming:
            segment_str = desc.model_dump_json(indent=2)
            print("STREAMED SEGMENT: ", segment_str)

    async def _run():
        with make_progress() as progress:
            task = progress.add_task("Processing and indexing video…", total=None)

            if description_attrs := list(args.attrs) if args.attrs else None:
                for attr in description_attrs:
                    if attr not in DEFAULT_DESCRIPTION_ATTRS:
                        err(f"Invalid attribute: {attr!r} — valid: {', '.join(sorted(DEFAULT_DESCRIPTION_ATTRS))}")

            video_id, indexed_count, result = await index_video(
                video_path=str(video_path),
                chunk_duration=chunk_sec,
                overlap=overlap_sec,
                description_attrs=description_attrs,
                include_summary=args.include_summary,
                on_segment=_on_segment,
            )
            progress.update(task, completed=True)
        return video_id, indexed_count, result

    try:
        video_id, indexed_count, result = asyncio.run(_run())
        console.print(f"\n[green]Indexed {indexed_count} chunks for video ID:[/green] {video_id}\n")
        print(result.model_dump_json(indent=2))
    except Exception as e:
        console.print(f"[red]Error indexing video: {e}[/red]")
        get_logger().exception("Error in index command")
        sys.exit(1)
    finally:
        TempPath.cleanup()
