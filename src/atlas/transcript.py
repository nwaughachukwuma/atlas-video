"""
Transcript processing using Groq Whisper API
"""

import asyncio
from typing import Literal, TypedDict

from groq import Groq

from .utils import (
    ChunkSlot,
    MediaChunk,
    MediaFileManager,
    RetryConfig,
    TempPath,
    delete_tmp_files,
    logger,
    process_time,
    retry,
    to_sexagesimal,
)


class TranscriptSegment(TypedDict):
    """Transcript segment from Whisper"""

    avg_logprob: float
    compression_ratio: float
    end: float
    id: int
    no_speech_prob: float
    seek: int
    start: float
    temperature: float
    text: str
    tokens: list[int]


class ProcessTranscriptResult(dict):
    """Transcript result with timing"""

    start: float
    end: float
    transcript: str


ReturnValue = Literal["text", "vtt", "srt", None]

WhisperModels = Literal["whisper-large-v3-turbo", "whisper-large-v3"]


class ProcessTranscript(MediaFileManager):
    """Process transcripts from media files using Groq Whisper"""

    chunk_duration = 60 * 10  # 10 minutes
    return_value: ReturnValue

    def __init__(self, file_path: str, return_value: ReturnValue = "text"):
        super().__init__(file_path)
        api_key = _get_groq_api_key()
        self.groq_client = Groq(api_key=api_key)
        self.return_value = return_value
        self.concurrency = self.max_workers
        self.ffmpeg_concurrency = min(5, self.max_workers // 2)

    async def __aenter__(self) -> "ProcessTranscript":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return True

    async def _split_media_file_to_chunks(self) -> list[MediaChunk]:
        """Split media file into chunks for processing"""
        if self.chunk_duration > self.duration:
            return [MediaChunk(path=self.file_path, start=0, end=self.duration)]

        semaphore = asyncio.Semaphore(self.ffmpeg_concurrency)

        async def __handler(slot: ChunkSlot) -> MediaChunk:
            async with semaphore:
                file_path = TempPath.get_path(ext=self.file_ext)
                chunk_path = await self._clip_media_async(
                    slot.start,
                    slot.end,
                    file_path,
                    use_audio=True,
                )
                return MediaChunk(path=chunk_path, start=slot.start, end=slot.end)

        slices = self._slice_media_file(self.chunk_duration)
        results = await asyncio.gather(
            *[__handler(s) for s in slices],
            return_exceptions=True,
        )

        clean_results = [r for r in results if isinstance(r, MediaChunk)]
        if len(slices) != len(clean_results):
            raise Exception("Error occurred splitting media file into chunks")

        return clean_results

    async def process(self) -> str:
        """Extract transcript from media file with controlled concurrency"""
        logger.info(f"Processing transcript for {self.file_path}")

        semaphore = asyncio.Semaphore(self.concurrency)

        async def _process_chunk(chunk: MediaChunk) -> ProcessTranscriptResult:
            async with semaphore:
                try:
                    transcript = await self._get_transcript(chunk.path, chunk.start)
                    return ProcessTranscriptResult(
                        start=chunk.start,
                        end=chunk.end,
                        transcript=transcript,
                    )
                except Exception as e:
                    logger.error(f"Error processing chunk: {e}")
                    raise e
                finally:
                    delete_tmp_files([chunk.path])

        # Split the media file into chunks and sort them
        results = await self._split_media_file_to_chunks()
        sorted_results = sorted(results, key=lambda v: v.start)

        # Process chunks concurrently
        gathered_results = await asyncio.gather(
            *[_process_chunk(c) for c in sorted_results],
            return_exceptions=True,
        )
        valid_gathered_results = [u for u in gathered_results if isinstance(u, ProcessTranscriptResult)]

        if len(valid_gathered_results) != len(sorted_results):
            raise Exception("Error occurred getting transcript for media file")

        # Sort results by start time and combine transcripts
        sorted_gathered_results = sorted(valid_gathered_results, key=lambda v: v.start)

        transcript = " ".join(v["transcript"] for v in sorted_gathered_results)

        if self.return_value == "srt":
            return self._vtt_to_srt(transcript)

        return transcript

    @process_time()
    async def _run_transcription_groq(
        self,
        model: WhisperModels,
        file_path: str,
        response_format: Literal["text", "json", "verbose_json"] = "verbose_json",
    ):
        """Run transcription using Groq Whisper API"""

        def _read_audio_file_sync(fp: str) -> tuple[str, bytes]:
            with open(fp, "rb") as audio_file:
                return (fp, audio_file.read())

        file_ref = await asyncio.to_thread(_read_audio_file_sync, file_path)

        @retry(RetryConfig(max_retries=2, delay=3, backoff=1.5))
        def _transcribe():
            try:
                return self.groq_client.audio.transcriptions.create(
                    file=file_ref,
                    model=model,
                    response_format=response_format,
                )
            except Exception as e:
                if model == "whisper-large-v3":
                    raise e
                # Fallback to whisper-large-v3
                return self.groq_client.audio.transcriptions.create(
                    file=file_ref,
                    model="whisper-large-v3",
                    response_format=response_format,
                )

        return await asyncio.to_thread(_transcribe)

    async def _get_transcript(self, file_path: str, time_offset: float = 0.0) -> str:
        """Get transcript for a media file chunk"""
        transcription = await self._run_transcription_groq("whisper-large-v3-turbo", file_path)
        result = transcription.model_dump()

        if self.return_value == "text":
            return result["text"]

        return self._segment_to_vtt(result["segments"], time_offset)

    def _segment_to_vtt(self, segments: list[TranscriptSegment], time_offset: float = 0.0) -> str:
        """Convert segments to VTT format"""
        vtt = "" if time_offset > 0.0 else "WEBVTT\n\n"
        for segment in segments:
            start = to_sexagesimal(round(segment["start"] + time_offset, 3))
            end = to_sexagesimal(round(segment["end"] + time_offset, 3))
            text = segment["text"]
            vtt += f"{start} --> {end}\n{text}\n\n"
        return vtt

    def _vtt_to_srt(self, vtt: str) -> str:
        """Convert VTT to SRT format"""
        vtt = vtt.strip()
        if vtt.startswith("WEBVTT"):
            vtt = vtt.replace("WEBVTT", "").strip()

        srt = ""
        for i, line in enumerate(vtt.split("\n\n")):
            if not line.strip():
                continue
            time_line, text = line.split("\n", 1)
            start, end = time_line.split(" --> ")
            start = start.replace(".", ",")
            end = end.replace(".", ",")
            srt += f"{i + 1}\n{start} --> {end}\n{text.strip()}\n\n"

        return srt.strip()


def _get_groq_api_key() -> str:
    """Get Groq API key from environment"""
    import os

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is required for transcription")
    return api_key
