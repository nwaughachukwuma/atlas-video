"""
Atlas CLI - Command line interface for multimodal video understanding
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from atlas import __version__

from .utils import DEFAULT_DESCRIPTION_ATTRS, DescriptionAttr, TempPath, logger

console = Console()


def validate_api_keys(require_gemini: bool = True, require_groq: bool = False) -> None:
    """Validate required API keys are set"""
    if require_gemini and not os.environ.get("GEMINI_API_KEY"):
        console.print("[red]Error: GEMINI_API_KEY environment variable is required[/red]")
        console.print("Set it with: export GEMINI_API_KEY=your-api-key")
        sys.exit(1)

    if require_groq and not os.environ.get("GROQ_API_KEY"):
        console.print("[red]Error: GROQ_API_KEY environment variable is required for transcription[/red]")
        console.print("Set it with: export GROQ_API_KEY=your-api-key")
        sys.exit(1)


def parse_duration(duration_str: str) -> int:
    """Parse duration string to seconds

    Examples:
        '15s' -> 15
        '1m' -> 60
        '1m30s' -> 90
    """
    duration_str = duration_str.strip().lower()

    if duration_str.endswith("s"):
        return int(duration_str[:-1])
    elif duration_str.endswith("m"):
        return int(duration_str[:-1]) * 60
    elif duration_str.endswith("h"):
        return int(duration_str[:-1]) * 3600
    else:
        try:
            return int(duration_str)
        except ValueError:
            console.print(f"[red]Invalid duration format: {duration_str}[/red]")
            console.print("Use format like: 15s, 1m, 1m30s")
            sys.exit(1)


def validate_video_path(video_path: str) -> Path:
    """Validate video file exists"""
    path = Path(video_path)
    if not path.exists():
        console.print(f"[red]Error: Video file not found: {video_path}[/red]")
        sys.exit(1)
    if not path.is_file():
        console.print(f"[red]Error: Not a file: {video_path}[/red]")
        sys.exit(1)
    return path


@click.group()
@click.version_option(version=__version__, prog_name="atlas")
def main():
    """
    Atlas - Multimodal insights engine for video understanding

    Extract rich multimodal insights from videos using AI.
    Requires GEMINI_API_KEY for video analysis and GROQ_API_KEY for transcription.
    """
    pass


@main.command()
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--chunk-duration", "-c", default="10s", help="Duration of each chunk (e.g., 15s, 1m)")
@click.option("--overlap", "-o", default="0s", help="Overlap between chunks (e.g., 1s, 5s)")
@click.option(
    "--attrs",
    "-a",
    multiple=True,
    help="Attributes to extract (visual_cues, interactions, contextual_information, audio_analysis, transcript)",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path (JSON format)")
@click.option("--format", "-f", type=click.Choice(["json", "text"]), default="text", help="Output format")
def extract(
    video_path: str,
    chunk_duration: str,
    overlap: str,
    attrs: tuple[str, ...],
    output: Optional[str],
    format: str,
):
    """
    Extract multimodal insights from a video.

    Analyzes video content and extracts visual cues, interactions,
    contextual information, audio analysis, and transcripts.

    Example:
        atlas extract video.mp4 --chunk-duration=15s --overlap=1s
    """
    validate_api_keys(require_gemini=True, require_groq=True)

    video_path = str(validate_video_path(video_path))
    chunk_sec = parse_duration(chunk_duration)
    overlap_sec = parse_duration(overlap)

    # Parse attributes
    description_attrs: list[DescriptionAttr] = list(attrs) if attrs else DEFAULT_DESCRIPTION_ATTRS

    # Validate attributes
    valid_attrs = set(DEFAULT_DESCRIPTION_ATTRS)
    for attr in description_attrs:
        if attr not in valid_attrs:
            console.print(f"[red]Invalid attribute: {attr}[/red]")
            console.print(f"Valid attributes: {', '.join(valid_attrs)}")
            sys.exit(1)

    console.print(f"[bold blue]Processing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]")

    async def run_extract():
        from .video_processor import VideoProcessor, VideoProcessorConfig

        config = VideoProcessorConfig(
            video_path=video_path,
            chunk_duration=chunk_sec,
            overlap=overlap_sec,
            description_attrs=description_attrs,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting insights...", total=None)

            async with VideoProcessor(config) as processor:
                result = await processor.process()

            progress.update(task, completed=True)

        return result

    try:
        result = asyncio.run(run_extract())

        if format == "json":
            output_data = result.model_dump()
            output_str = json.dumps(output_data, indent=2)

            if output:
                Path(output).write_text(output_str)
                console.print(f"[green]Results saved to:[/green] {output}")
            else:
                print(output_str)
        else:
            # Text format
            console.print(f"\n[bold green]Results for {video_path}[/bold green]")
            console.print(f"Duration: {result.duration:.2f}s")
            console.print(f"Segments: {len(result.video_descriptions)}\n")

            for desc in result.video_descriptions:
                console.print(f"[bold cyan]Segment {desc.start:.1f}s - {desc.end:.1f}s[/bold cyan]")
                for analysis in desc.video_analysis:
                    attr_label = " ".join(analysis.attr.upper().split("_"))
                    console.print(f"  [yellow]{attr_label}:[/yellow] {analysis.value[:200]}...")
                console.print()

            if output:
                output_data = result.model_dump()
                Path(output).write_text(json.dumps(output_data, indent=2))
                console.print(f"[green]Full results saved to:[/green] {output}")

    except Exception as e:
        console.print(f"[red]Error processing video: {e}[/red]")
        logger.exception("Error in extract command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


@main.command()
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--chunk-duration", "-c", default="10s", help="Duration of each chunk (e.g., 15s, 1m)")
@click.option("--overlap", "-o", default="0s", help="Overlap between chunks (e.g., 1s, 5s)")
@click.option("--store-path", "-s", type=click.Path(), help="Path to store the vector index")
@click.option("--embedding-dim", "-e", default=768, help="Embedding dimension (768 or 3072)")
def index(
    video_path: str,
    chunk_duration: str,
    overlap: str,
    store_path: Optional[str],
    embedding_dim: int,
):
    """
    Index a video for semantic search.

    Processes the video and stores embeddings in a local vector store
    for fast semantic search.

    Example:
        atlas index video.mp4 --chunk-duration=15s --overlap=1s
    """
    validate_api_keys(require_gemini=True, require_groq=True)

    video_path = str(validate_video_path(video_path))
    chunk_sec = parse_duration(chunk_duration)
    overlap_sec = parse_duration(overlap)

    console.print(f"[bold blue]Indexing video:[/bold blue] {video_path}")
    console.print(f"[dim]Chunk duration: {chunk_sec}s, Overlap: {overlap_sec}s[/dim]")

    async def run_index():
        from .vector_store import index_video

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing and indexing video...", total=None)

            indexed_count, result = await index_video(
                video_path=video_path,
                chunk_duration=chunk_sec,
                overlap=overlap_sec,
                store_path=store_path,
            )

            progress.update(task, completed=True)

        return indexed_count, result

    try:
        indexed_count, result = asyncio.run(run_index())

        console.print("\n[bold green]Indexing complete![/bold green]")
        console.print(f"  Video: {video_path}")
        console.print(f"  Duration: {result.duration:.2f}s")
        console.print(f"  Segments processed: {len(result.video_descriptions)}")
        console.print(f"  Documents indexed: {indexed_count}")

        if store_path:
            console.print(f"  Index location: {store_path}")
        else:
            console.print("  Index location: ~/.atlas/index")

    except Exception as e:
        console.print(f"[red]Error indexing video: {e}[/red]")
        logger.exception("Error in index command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


@main.command()
@click.argument("query")
@click.option("--top-k", "-k", default=10, help="Number of results to return")
@click.option("--video", "-v", type=click.Path(), help="Filter by video path")
@click.option("--store-path", "-s", type=click.Path(), help="Path to the vector index")
def search(query: str, top_k: int, video: Optional[str], store_path: Optional[str]):
    """
    Search indexed videos semantically.

    Performs semantic search over indexed video content.

    Example:
        atlas search "people discussing AI"
    """
    validate_api_keys(require_gemini=True, require_groq=False)

    async def run_search():
        from .vector_store import search_video

        return await search_video(
            query=query,
            top_k=top_k,
            video_filter=video,
            store_path=store_path,
        )

    try:
        results = asyncio.run(run_search())

        if not results:
            console.print("[yellow]No results found[/yellow]")
            console.print("Make sure you have indexed some videos first with 'atlas index'")
            return

        console.print(f"\n[bold green]Found {len(results)} results for:[/bold green] '{query}'\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Video", width=30)
        table.add_column("Time", width=15)
        table.add_column("Content", width=50)

        for i, result in enumerate(results, 1):
            time_str = f"{result.start:.1f}s - {result.end:.1f}s"
            content = result.content[:47] + "..." if len(result.content) > 50 else result.content
            video_name = (
                Path(result.video_path).name[:27] + "..."
                if len(result.video_path) > 30
                else Path(result.video_path).name
            )

            table.add_row(
                str(i),
                f"{result.score:.3f}",
                video_name,
                time_str,
                content,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error searching: {e}[/red]")
        logger.exception("Error in search command")
        sys.exit(1)


@main.command()
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--format", "-f", type=click.Choice(["text", "vtt", "srt"]), default="text", help="Output format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def transcribe(video_path: str, format: str, output: Optional[str]):
    """
    Extract transcript from a video or audio file.

    Uses Groq Whisper for fast transcription.

    Example:
        atlas transcribe video.mp4 --format=srt --output=transcript.srt
    """
    validate_api_keys(require_gemini=False, require_groq=True)

    video_path = str(validate_video_path(video_path))

    console.print(f"[bold blue]Transcribing:[/bold blue] {video_path}")
    console.print(f"[dim]Output format: {format}[/dim]")

    async def run_transcribe():
        from .video_processor import extract_transcript

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Transcribing...", total=None)
            result = await extract_transcript(video_path, format=format)
            progress.update(task, completed=True)

        return result

    try:
        result = asyncio.run(run_transcribe())

        if output:
            Path(output).write_text(result)
            console.print(f"[green]Transcript saved to:[/green] {output}")
        else:
            console.print("\n[bold green]Transcript:[/bold green]")
            print(result)

    except Exception as e:
        console.print(f"[red]Error transcribing: {e}[/red]")
        logger.exception("Error in transcribe command")
        sys.exit(1)
    finally:
        TempPath.cleanup()


@main.command()
def stats():
    """
    Show statistics about the local vector store.

    Example:
        atlas stats
    """
    from .vector_store import VectorStore

    store = VectorStore()
    stats_data = store.get_stats()

    console.print("\n[bold blue]Atlas Vector Store Statistics[/bold blue]\n")

    table = Table(show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    for key, value in stats_data.items():
        table.add_row(key, str(value))

    console.print(table)


if __name__ == "__main__":
    main()
