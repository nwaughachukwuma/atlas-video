"""
Video processor for multimodal analysis
"""

import asyncio
from typing import Callable, Optional

from google.genai import types
from pydantic import BaseModel

from .gemini_client import GeminiMediaEngine
from .media_manager import MediaFileManager
from .prompts import VideoPrompt, video_analysis_prompts, video_system_prompt
from .transcript import get_video_transcript
from .utils import (
    DEFAULT_DESCRIPTION_ATTRS,
    ChunkSlot,
    DescriptionAttr,
    MediaChunk,
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
    include_summary: bool = True


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
        MediaFileManager.__init__(self, config.video_path)
        GeminiMediaEngine.__init__(self)

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
    async def process(
        self,
        on_segment: Optional[Callable[[VideoDescription], None]] = None,
    ) -> VideoProcessorResult:
        """Process video and extract multimodal features with controlled concurrency

        Call *on_segment* for each segment as soon as it completes.
        Segments are delivered in completion order (not necessarily chronological),
        but the final VideoProcessorResult contains them sorted by start time.

        Args:
            on_segment: Callback invoked synchronously with each VideoDescription as it completes.
            The callback runs in the event loop thread. (Wrap each task so we invoke the callback as each one settles)

        Returns:
            VideoProcessorResult with all descriptions sorted by start time.
        """
        logger.info(f"Processing video: {self.video_path}")
        semaphore = asyncio.Semaphore(self.concurrency)

        @retry(RetryConfig(max_retries=1, delay=5, backoff=1.5))
        async def __process_handler(video_chunk: MediaChunk) -> VideoDescription:
            async with semaphore:
                try:
                    result = await self.analyze_video_chunk(video_chunk)
                    if on_segment:
                        on_segment(result)
                    return result
                finally:
                    delete_tmp_files([video_chunk.path])

        video_chunks = await self._get_video_chunks()
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
    async def get_transcript(self):
        """Get transcript for the entire video"""
        return await get_video_transcript(self.video_path)

    async def analyze_chunk_content(self, file_part: types.Part, chunk_path: str) -> list[VideoAttrAnalysis]:
        """Analyze video content and extract features."""

        async def handler(video_prompt: VideoPrompt) -> VideoAttrAnalysis:
            try:
                if video_prompt.attr == "transcript":
                    description = await get_video_transcript(chunk_path)
                else:
                    description = await self.describe_media_from_file(
                        file_part,
                        video_system_prompt(
                            video_prompt.value,
                            video_prompt.attr,
                        ),
                    )
            except Exception as e:
                logger.error(f"Error getting video chunk analysis: {e}")
                description = ""

            return VideoAttrAnalysis(
                value=description,
                attr=video_prompt.attr,
            )

        return await asyncio.gather(
            *[handler(v) for v in video_analysis_prompts if v.attr in self.description_attrs],
        )

    @process_time()
    async def analyze_video_chunk(self, chunk: MediaChunk) -> VideoDescription:
        """Analyze video chunk and extract features"""
        logger.info(f"Analyzing video chunk: {chunk.path}")
        try:
            file_part = await self.get_file_part(chunk.path, "video/mp4")
            result = await self.analyze_chunk_content(file_part, chunk.path)
        except Exception as e:
            logger.error(f"Error analyzing video chunk: {e}")
            result = []

        return VideoDescription(
            start=chunk.start,
            end=chunk.end,
            video_analysis=result,
        )
