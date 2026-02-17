"""
Video processor for multimodal analysis
"""

import asyncio
from typing import Optional

from pydantic import BaseModel

from .gemini_client import GeminiMediaEngine
from .prompts import VideoPrompt, video_analysis_prompts, video_system_prompt
from .transcript import ProcessTranscript
from .utils import (
    DEFAULT_DESCRIPTION_ATTRS,
    ChunkSlot,
    DescriptionAttr,
    MediaChunk,
    MediaFileManager,
    RetryConfig,
    TempPath,
    VideoAttrAnalysis,
    delete_tmp_files,
    logger,
    process_time,
    retry,
)


class VideoProcessorConfig(BaseModel):
    """Configuration for video processing"""

    video_path: str
    chunk_duration: int = 10  # seconds
    overlap: int = 0  # seconds
    description_attrs: Optional[list[DescriptionAttr]] = None
    include_summary: bool = False


class VideoDescription(BaseModel):
    """Video description for a time segment"""

    start: float
    end: float
    summary: Optional[str] = None
    video_analysis: list[VideoAttrAnalysis]


class VideoProcessorResult(BaseModel):
    """Result of video processing"""

    video_path: str
    duration: float
    transcript: str = ""
    video_descriptions: list[VideoDescription]


class VideoProcessor(MediaFileManager, GeminiMediaEngine):
    """Process videos for multimodal analysis"""

    def __init__(self, config: VideoProcessorConfig):
        GeminiMediaEngine.__init__(self)
        MediaFileManager.__init__(self, config.video_path)

        self.concurrency = self.max_workers
        self.ffmpeg_concurrency = min(5, self.concurrency // 2)

        self.video_path = config.video_path
        self.chunk_duration = config.chunk_duration
        self.overlap = config.overlap
        self.description_attrs = config.description_attrs or DEFAULT_DESCRIPTION_ATTRS
        self.include_summary = config.include_summary

    async def __aenter__(self) -> "VideoProcessor":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return True

    @process_time()
    async def process(self) -> VideoProcessorResult:
        """Process video and extract multimodal features with controlled concurrency"""
        logger.info(f"Processing video: {self.video_path}")

        semaphore = asyncio.Semaphore(self.concurrency)

        @retry(RetryConfig(max_retries=1, delay=5, backoff=1.5))
        async def __process_handler(video_chunk: MediaChunk) -> VideoDescription:
            async with semaphore:
                try:
                    return await self._analyze_video_chunk(video_chunk)
                finally:
                    delete_tmp_files([video_chunk.path])

        video_chunks = await self._get_video_chunks()

        # Process all chunks concurrently with controlled concurrency via semaphore
        tasks_results = await asyncio.gather(
            *[__process_handler(vc) for vc in video_chunks],
            return_exceptions=True,
        )

        sorted_results = sorted(
            (r for r in tasks_results if isinstance(r, VideoDescription)),
            key=lambda v: v.start,
        )

        return VideoProcessorResult(
            video_path=self.video_path,
            duration=self.duration,
            transcript="",
            video_descriptions=sorted_results,
        )

    async def _get_video_chunks(self) -> list[MediaChunk]:
        """Generate video chunks for parallel processing"""
        semaphore = asyncio.Semaphore(self.ffmpeg_concurrency)

        async def _get_media_chunk(slot: ChunkSlot) -> MediaChunk:
            async with semaphore:
                file_path = TempPath.get_path(ext=".mp4")
                chunk_path = await self._clip_media_async(slot.start, slot.end, file_path)
                return MediaChunk(path=chunk_path, start=slot.start, end=slot.end)

        # Calculate all slots upfront
        chunk_slots = self._slice_media_file(self.chunk_duration, self.overlap)

        tasks = [_get_media_chunk(c) for c in chunk_slots]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        clean_results = [v for v in results if isinstance(v, MediaChunk)]

        # Ensure all video chunks are successfully clipped
        if len(chunk_slots) != len(clean_results):
            errored = [v for v in results if isinstance(v, BaseException)]
            logger.error(f"Failed to process {len(errored)}/{len(chunk_slots)}. Errored Chunks: {errored}")
            raise Exception(f"Error while splitting video. Failed to process {len(errored)}/{len(chunk_slots)} chunks")

        if len(clean_results) == 0:
            raise Exception("Error while splitting video. All chunks failed to process")

        return clean_results

    @process_time()
    async def _get_transcript(self) -> str:
        """Get transcript for the entire video"""
        async with ProcessTranscript(self.video_path, return_value="text") as processor:
            return await processor.process()

    async def _analyze_video_content(self, file_part, file_path: str) -> list[VideoAttrAnalysis]:
        """Analyze video content and extract features"""

        async def handler(video_prompt: VideoPrompt) -> VideoAttrAnalysis:
            try:
                if video_prompt.attr == "transcript":
                    # Use local transcription via Groq
                    from .transcript import ProcessTranscript

                    async with ProcessTranscript(file_path, return_value="text") as proc:
                        description = await proc.process()
                else:
                    description = await self.describe_media_from_file(
                        file_part,
                        video_system_prompt(video_prompt.value, video_prompt.attr),
                    )
            except Exception as e:
                logger.error(f"Error getting video chunk analysis: {e}")
                description = ""
            return VideoAttrAnalysis(value=description, attr=video_prompt.attr)

        return await asyncio.gather(
            *[handler(v) for v in video_analysis_prompts if v.attr in self.description_attrs],
        )

    @process_time()
    async def _analyze_video_chunk(self, chunk: MediaChunk) -> VideoDescription:
        """Analyze video chunk and extract features"""
        logger.info(f"Analyzing video chunk: {chunk.path}")
        try:
            file_part = await self.get_file_part(chunk.path, "video/mp4")
            result = await self._analyze_video_content(file_part, chunk.path)
        except Exception as e:
            logger.error(f"Error analyzing video chunk: {e}")
            result = []

        return VideoDescription(
            start=chunk.start,
            end=chunk.end,
            video_analysis=result,
        )


async def extract_video_insights(
    video_path: str,
    chunk_duration: int = 10,
    overlap: int = 0,
    description_attrs: Optional[list[DescriptionAttr]] = None,
) -> VideoProcessorResult:
    """Convenience function to extract insights from a video

    Args:
        video_path: Path to the video file
        chunk_duration: Duration of each chunk in seconds
        overlap: Overlap between chunks in seconds
        description_attrs: List of attributes to extract

    Returns:
        VideoProcessorResult with multimodal insights
    """
    config = VideoProcessorConfig(
        video_path=video_path,
        chunk_duration=chunk_duration,
        overlap=overlap,
        description_attrs=description_attrs,
    )

    async with VideoProcessor(config) as processor:
        return await processor.process()


async def extract_transcript(video_path: str, format: str = "text") -> str:
    """Extract transcript from a video file

    Args:
        video_path: Path to the video file
        format: Output format ('text', 'vtt', or 'srt')

    Returns:
        Transcript in the specified format
    """
    return_value = format if format in ("text", "vtt", "srt") else "text"
    async with ProcessTranscript(video_path, return_value=return_value) as processor:
        return await processor.process()
