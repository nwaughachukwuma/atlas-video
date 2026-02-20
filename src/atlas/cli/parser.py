"""Argument parser construction for the Atlas CLI.

This is isolated so that ``--help`` and ``--version`` stay fast — no heavy
dependency is imported at the module level.
"""

from __future__ import annotations

import argparse

from .cmd_explore import _cmd_chat, _cmd_get_data, _cmd_list_chat, _cmd_list_videos, _cmd_search, _cmd_stats
from .cmd_media import _cmd_extract, _cmd_index, _cmd_transcribe

VERSION = "0.1.0"
PROG_NAME = "atlas"


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the full ``argparse`` parser for every sub-command."""
    # Shared parent that injects --benchmark, --no-queue, --no-streaming.
    _shared = argparse.ArgumentParser(add_help=False)
    _shared.add_argument(
        "--benchmark",
        action="store_true",
        default=False,
        help="Print a per-function timing breakdown after the command completes.",
    )
    _shared.add_argument(
        "--no-queue",
        action="store_true",
        default=False,
        dest="no_queue",
        help="Run immediately without queuing (default: queue task).",
    )
    _shared.add_argument(
        "--no-streaming",
        action="store_true",
        default=False,
        dest="no_streaming",
        help="Disable real-time streaming output for queued tasks.",
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
            "  atlas index video.mp4\n"
            "  atlas search 'people discussing AI'\n"
            "  atlas search abc123 'people discussing AI'\n"
            "  atlas chat abc123 'What is this video about?'\n"
            "  atlas get-video abc123\n"
            "  atlas list-videos\n"
            "  atlas list-chat abc123\n"
            "  atlas stats\n"
            "  atlas queue list\n"
            "  atlas queue status --task-id abc123\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"atlas {VERSION}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # ── extract ───────────────────────────────────────────────────────
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
        help=(
            "Attribute to extract; repeat for multiple "
            "(visual_cues, interactions, contextual_information, audio_analysis, transcript)."
        ),
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

    # ── index ─────────────────────────────────────────────────────────
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
    p_index.add_argument(
        "--embedding-dim",
        "-e",
        type=int,
        default=768,
        metavar="N",
        help="Embedding dimension: 768 or 3072 (default: 768).",
    )
    p_index.add_argument(
        "--attrs",
        "-a",
        action="append",
        metavar="ATTR",
        help=(
            "Attribute to extract; repeat for multiple "
            "(visual_cues, interactions, contextual_information, audio_analysis, transcript)."
        ),
    )
    p_index.add_argument(
        "--include-summary",
        action="store_true",
        default=True,
        dest="include_summary",
        help="Generate a summary for each segment (default: enabled).",
    )
    p_index.add_argument(
        "--no-summary",
        action="store_false",
        dest="include_summary",
        help="Disable per-segment summary generation.",
    )
    p_index.set_defaults(func=_cmd_index)

    # ── search ────────────────────────────────────────────────────────
    p_search = sub.add_parser(
        "search",
        help="Search indexed videos semantically.",
        description="Run a natural-language query against previously indexed videos.",
        epilog=("Examples:\n  atlas search 'people discussing AI'\n  atlas search abc123 'people discussing AI'"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_search.add_argument(
        "search_args",
        nargs="+",
        metavar="ARG",
        help="[VIDEO_ID] QUERY — optional video ID followed by a natural-language query.",
    )
    p_search.add_argument(
        "--top-k", "-k", type=int, default=10, metavar="N", help="Number of results to return (default: 10)."
    )
    p_search.set_defaults(func=_cmd_search)

    # ── transcribe ────────────────────────────────────────────────────
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

    # ── chat ──────────────────────────────────────────────────────────
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
    p_chat.set_defaults(func=_cmd_chat)

    # ── list-videos ───────────────────────────────────────────────────
    p_list_videos = sub.add_parser(
        "list-videos",
        help="List all indexed videos.",
        description="Display all videos that have been indexed in the local vector store.",
        epilog="Example:\n  atlas list-videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_list_videos.set_defaults(func=_cmd_list_videos)

    # ── list-chat ─────────────────────────────────────────────────────
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
    p_list_chat.set_defaults(func=_cmd_list_chat)

    # ── stats ─────────────────────────────────────────────────────────
    p_stats = sub.add_parser(
        "stats",
        help="Show statistics about the local vector store.",
        description="Display key metrics about the local Atlas vector index.",
        epilog="Example:\n  atlas stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_shared],
    )
    p_stats.set_defaults(func=_cmd_stats)

    # ── get-video ─────────────────────────────────────────────────────────
    p_get_video = sub.add_parser(
        "get-video",
        help="Retrieve all indexed data for a video.",
        description=(
            "Fetch all stored data for a video ID and return it in the same shape as the 'extract' command.\n"
            "Outputs JSON to stdout, or to a file with --output."
        ),
        epilog="Examples:\n  atlas get-video abc123\n  atlas get-video abc123 --output data.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_get_video.add_argument("video_id", help="Video ID returned by 'atlas index'.")
    p_get_video.add_argument("--output", "-o", metavar="FILE", help="Save JSON output to this file.")
    p_get_video.set_defaults(func=_cmd_get_data)

    # ── queue ─────────────────────────────────────────────────────────
    from ..task_queue import add_queue_commands as _add_queue_commands

    _add_queue_commands(sub)

    return parser
