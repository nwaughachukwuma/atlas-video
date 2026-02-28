"""Queue-worker task functions — self-contained, no rich output.

Each ``_run_*`` function accepts an ``argparse.Namespace`` and returns a
serialisable result (``str`` or ``dict``).  They are designed to run inside
a detached worker subprocess and must never import ``rich``.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING, List

from .helpers import parse_duration

if TYPE_CHECKING:
    from ..utils import DescriptionAttr


def run_extract(args: argparse.Namespace) -> dict:
    """Run extract in a queue worker thread.  Returns a JSON-serialisable dict."""
    from ..utils import DEFAULT_DESCRIPTION_ATTRS
    from ..video_processor import VideoProcessor, VideoProcessorConfig

    video_path = str(getattr(args, "_video_path_resolved", args.video_path))
    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)

    if args.attrs:
        for attr in list(args.attrs):
            if attr not in DEFAULT_DESCRIPTION_ATTRS:
                raise ValueError(f"Invalid attribute: {attr!r}")
        description_attrs: List[DescriptionAttr] = list(args.attrs)
    else:
        description_attrs = DEFAULT_DESCRIPTION_ATTRS

    async def _run():
        config = VideoProcessorConfig(
            video_path=video_path,
            chunk_duration=chunk_sec,
            overlap=overlap_sec,
            description_attrs=description_attrs,
            include_summary=args.include_summary,
        )
        async with VideoProcessor(config) as processor:
            return await processor.process()

    result = asyncio.run(_run())
    if not result:
        raise ValueError(f"No `extract` result returned from processing {video_path}")
    return result.model_dump()


def run_transcribe(args: argparse.Namespace) -> dict:
    """Run transcribe in a queue worker thread.  Returns a JSON-serialisable dict."""
    from ..transcript import get_video_transcript

    fmt = args.format
    video_path = str(getattr(args, "_video_path_resolved", args.video_path))

    async def _run():
        return await get_video_transcript(video_path, format=fmt)

    result = asyncio.run(_run())
    if not result.strip():
        raise ValueError(f"No transcript content generated for {video_path}")
    return {"transcript": result, "format": fmt}


def run_index(args: argparse.Namespace) -> dict:
    """Run index in a queue worker thread.  Returns a JSON-serialisable dict."""
    from ..utils import DEFAULT_DESCRIPTION_ATTRS
    from ..vector_store.video_index import index_video

    video_path = str(getattr(args, "_video_path_resolved", args.video_path))
    chunk_sec = parse_duration(args.chunk_duration)
    overlap_sec = parse_duration(args.overlap)

    if args.attrs:
        for attr in list(args.attrs):
            if attr not in DEFAULT_DESCRIPTION_ATTRS:
                raise ValueError(f"Invalid attribute: {attr!r}")
        description_attrs = list(args.attrs)
    else:
        description_attrs = DEFAULT_DESCRIPTION_ATTRS

    async def _run():
        video_id, indexed_count, result = await index_video(
            video_path=video_path,
            chunk_duration=chunk_sec,
            overlap=overlap_sec,
            description_attrs=description_attrs,
            include_summary=args.include_summary,
        )
        return video_id, indexed_count, result

    video_id, indexed_count, result = asyncio.run(_run())
    return {
        "video_id": video_id,
        "indexed_count": indexed_count,
        "result": result.model_dump(),
    }
