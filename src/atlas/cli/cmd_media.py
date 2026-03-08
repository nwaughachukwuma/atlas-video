"""
Command handlers for extract, transcribe, and index (the "heavy" video commands)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, List, Optional

from .helpers import (
    err,
    make_progress,
    parse_duration,
    print_saved_run_info,
    print_queued_info,
    validate_api_keys,
    validate_video_path,
)

if TYPE_CHECKING:
    from ..utils import DescriptionAttr


def _start_direct_run(command: str, video_path: Path, output_path: Optional[str], benchmark: bool) -> tuple[str, object]:
    """Create and mark running a persisted direct-run record."""
    from ..task_queue import TaskStore
    from ..uuid import uuid

    run_id = uuid(10)
    store = TaskStore()
    store.add(
        run_id,
        command,
        f"{command} {video_path.name}",
        output_path=output_path,
        benchmark=benchmark,
        run_type="direct",
    )
    store.mark_running(run_id)
    return run_id, store


# ── extract ───────────────────────────────────────────────────────────────────


def cmd_extract(args: argparse.Namespace) -> dict[str, object] | None:
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
        from ..task_queue import benchmark_file_for, get_queue, output_file_for

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
        return {
            "id": task_id,
            "task_id": task_id,
            "run_type": "queued",
            "command": "extract",
            "output_path": str(output_file_for(task_id)),
            **({"requested_output_path": output_path} if output_path else {}),
            **({"benchmark_path": str(benchmark_file_for(task_id))} if benchmark else {}),
        }

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
    run_id, store = _start_direct_run("extract", video_path, output_path, benchmark)
    t_start = perf_counter()

    console.print(f"\n[bold blue]Processing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]\n")

    def _on_segment(desc: VideoDescription) -> None:
        if not no_streaming:
            segment_str = desc.model_dump_json(indent=2)
            console.print("STREAMED SEGMENT: ", segment_str)

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
        if not result:
            from ..task_queue import persist_result

            content, result_path = persist_result(run_id, {"error": "No insights extracted from the video."})
            store.mark_failed(run_id, "No insights extracted from the video.", result_text=content, result_path=result_path)
            err("No insights extracted from the video.")

        output_str = result.model_dump_json(indent=2)
        from ..task_queue import persist_benchmark, persist_result

        content, result_path = persist_result(run_id, result, output_path=output_path, user_content=output_str)
        benchmark_text, benchmark_path = (None, None)
        if benchmark:
            benchmark_text, benchmark_path = persist_benchmark(run_id, total_s=perf_counter() - t_start)
        store.mark_completed(
            run_id,
            result_text=content,
            result_path=result_path,
            benchmark_text=benchmark_text,
            benchmark_path=benchmark_path,
        )
        print_saved_run_info(
            console,
            run_id,
            "extract",
            output_path=result_path,
            requested_output_path=output_path,
            benchmark_path=benchmark_path,
        )
        payload = {
            **result.model_dump(),
            "id": run_id,
            "run_type": "direct",
            "command": "extract",
            "output_path": result_path,
        }
        if output_path:
            payload["requested_output_path"] = output_path
        if benchmark_path:
            payload["benchmark_path"] = benchmark_path
        if not output_path:
            print(output_str)
        return payload
    except Exception as e:
        from ..task_queue import persist_result

        error_payload = {"error": f"{type(e).__name__}: {e}"}
        content, result_path = persist_result(run_id, error_payload, output_path=output_path)
        store.mark_failed(run_id, error_payload["error"], result_text=content, result_path=result_path)
        console.print(f"[red]Error processing video: {e}[/red]")
        get_logger().exception("Error in extract command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


# ── transcribe ────────────────────────────────────────────────────────────────


def cmd_transcribe(args: argparse.Namespace) -> dict[str, object] | None:
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
        from ..task_queue import benchmark_file_for, get_queue, output_file_for

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
        return {
            "id": task_id,
            "task_id": task_id,
            "run_type": "queued",
            "command": "transcribe",
            "output_path": str(output_file_for(task_id)),
            **({"requested_output_path": output_path} if output_path else {}),
            **({"benchmark_path": str(benchmark_file_for(task_id))} if benchmark else {}),
        }

    # ── Direct execution (no queue) ───────────────────────────────────
    from rich.console import Console

    from ..transcript import get_video_transcript

    console = Console(stderr=True)
    run_id, store = _start_direct_run("transcribe", video_path, output_path, benchmark)
    t_start = perf_counter()

    console.print(f"\n[bold blue]Transcribing:[/bold blue] {video_path}")
    console.print(f"[dim]Output format: {fmt}[/dim]\n")

    def _on_chunk(text: str) -> None:
        if not no_streaming:
            console.print("STREAMED CHUNK:", text)

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
            from ..task_queue import persist_result

            content, result_path = persist_result(
                run_id,
                {"error": "No transcript content generated."},
                output_path=output_path,
            )
            store.mark_failed(run_id, "No transcript content generated.", result_text=content, result_path=result_path)
            return None

        result = {"transcript": full_text, "format": fmt}
        from ..task_queue import persist_benchmark, persist_result

        content, result_path = persist_result(run_id, result, output_path=output_path, user_content=full_text)
        benchmark_text, benchmark_path = (None, None)
        if benchmark:
            benchmark_text, benchmark_path = persist_benchmark(run_id, total_s=perf_counter() - t_start)
        store.mark_completed(
            run_id,
            result_text=content,
            result_path=result_path,
            benchmark_text=benchmark_text,
            benchmark_path=benchmark_path,
        )
        print_saved_run_info(
            console,
            run_id,
            "transcribe",
            output_path=result_path,
            requested_output_path=output_path,
            benchmark_path=benchmark_path,
        )
        payload = {
            **result,
            "id": run_id,
            "run_type": "direct",
            "command": "transcribe",
            "output_path": result_path,
        }
        if output_path:
            payload["requested_output_path"] = output_path
        if benchmark_path:
            payload["benchmark_path"] = benchmark_path
        if not output_path:
            print(json.dumps(result, indent=2))
        return payload
    except Exception as e:
        from ..task_queue import persist_result

        error_payload = {"error": f"{type(e).__name__}: {e}"}
        content, result_path = persist_result(run_id, error_payload, output_path=output_path)
        store.mark_failed(run_id, error_payload["error"], result_text=content, result_path=result_path)
        console.print(f"[red]Error transcribing: {e}[/red]")
        get_logger().exception("Error in transcribe command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


# ── index ─────────────────────────────────────────────────────────────────────


def cmd_index(args: argparse.Namespace) -> dict[str, object] | None:
    """Index a video for semantic search, optionally queuing the task."""
    from . import get_console, get_logger
    from ..utils import TempPath

    console = get_console()
    use_queue = not getattr(args, "no_queue", False)
    no_streaming = getattr(args, "no_streaming", False)
    benchmark = getattr(args, "benchmark", False)
    output_path: Optional[str] = getattr(args, "output", None)

    validate_api_keys(require_gemini=True, require_groq=True)
    video_path = validate_video_path(args.video_path)
    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)

    if use_queue:
        from ..task_queue import benchmark_file_for, get_queue, output_file_for

        queue = get_queue()
        args_copy = argparse.Namespace(**vars(args))
        args_copy._video_path_resolved = str(video_path)

        task_id = queue.submit(
            args_copy,
            command="index",
            label=f"index {video_path.name}",
            output_path=output_path,
            benchmark=benchmark,
        )
        print_queued_info(console, task_id, "index", output_path=output_path, benchmark=benchmark)
        return {
            "id": task_id,
            "task_id": task_id,
            "run_type": "queued",
            "command": "index",
            "output_path": str(output_file_for(task_id)),
            **({"requested_output_path": output_path} if output_path else {}),
            **({"benchmark_path": str(benchmark_file_for(task_id))} if benchmark else {}),
        }

    # ── Direct execution (no queue) ───────────────────────────────────
    from rich.console import Console

    from ..utils import DEFAULT_DESCRIPTION_ATTRS
    from ..vector_store.video_index import index_video
    from ..video_processor import VideoDescription

    console = Console(stderr=True)
    run_id, store = _start_direct_run("index", video_path, output_path, benchmark)
    t_start = perf_counter()

    console.print(f"\n[bold blue]Indexing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]")

    def _on_segment(desc: VideoDescription) -> None:
        if not no_streaming:
            segment_str = desc.model_dump_json(indent=2)
            console.print(f"STREAMED SEGMENT: {segment_str} ")

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
        # console.print(f"\n[green]Indexed {indexed_count} chunks for video ID:[/green] {video_id}\n")
        # print(result.model_dump_json(indent=2))
        output = {
            "video_id": video_id,
            "indexed_count": indexed_count,
            "result": result.model_dump(),
        }
        from ..task_queue import persist_benchmark, persist_result

        output_str = json.dumps(output, indent=2)
        content, result_path = persist_result(run_id, output, output_path=output_path, user_content=output_str)
        benchmark_text, benchmark_path = (None, None)
        if benchmark:
            benchmark_text, benchmark_path = persist_benchmark(run_id, total_s=perf_counter() - t_start)
        store.mark_completed(
            run_id,
            result_text=content,
            result_path=result_path,
            benchmark_text=benchmark_text,
            benchmark_path=benchmark_path,
        )
        print_saved_run_info(
            console,
            run_id,
            "index",
            output_path=result_path,
            requested_output_path=output_path,
            benchmark_path=benchmark_path,
        )
        payload = {
            **output,
            "id": run_id,
            "run_type": "direct",
            "command": "index",
            "output_path": result_path,
        }
        if output_path:
            payload["requested_output_path"] = output_path
        if benchmark_path:
            payload["benchmark_path"] = benchmark_path
        print(output_str)
        return payload
    except Exception as e:
        from ..task_queue import persist_result

        error_payload = {"error": f"{type(e).__name__}: {e}"}
        content, result_path = persist_result(run_id, error_payload, output_path=output_path)
        store.mark_failed(run_id, error_payload["error"], result_text=content, result_path=result_path)
        console.print(f"[red]Error indexing video: {e}[/red]")
        get_logger().exception("Error in index command")
        sys.exit(1)
    finally:
        TempPath.cleanup()
