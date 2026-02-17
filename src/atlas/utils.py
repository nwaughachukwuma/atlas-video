"""
Core utilities for Atlas
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from time import sleep, time
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel

from .logger import logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("atlas")

T = TypeVar("T")


def process_time():
    """Print process execution time for a given function"""

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time()
                response = await func(*args, **kwargs)

                time_diff = f"{(time() - start_time):.2f}s"
                logger.info(f"{func.__name__} completed in {time_diff}")

                return response

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time()
            response = func(*args, **kwargs)

            time_diff = f"{(time() - start_time):.2f}s"
            logger.info(f"{func.__name__} completed in {time_diff}")

            return response

        return wrapper

    return decorator


@dataclass
class RetryConfig:
    max_retries: int = 3
    delay: float = 1.0
    backoff: float = 2.0


def retry(retry_config: RetryConfig | None, default_return: Any = None):
    """
    Retry logic for async functions with exponential backoff.
    """
    config = retry_config or RetryConfig()

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async def _async_retry():
                    delay = config.delay
                    last_exception = None
                    for attempt in range(config.max_retries + 1):
                        try:
                            return await func(*args, **kwargs)
                        except Exception as e:
                            last_exception = e
                            if attempt == 0:
                                logger.warning(f"Request Failed: {e}. Retrying...")
                            else:
                                logger.warning(f"Retry attempt {attempt}/{config.max_retries} failed: {e}")

                            if attempt < config.max_retries:  # Don't sleep after last attempt
                                await asyncio.sleep(delay)
                                if config.backoff:
                                    delay *= config.backoff

                    # If default_return is None and we have an exception, re-raise it
                    if default_return is None and last_exception:
                        raise last_exception
                    return default_return

                return await _async_retry()

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            def _sync_retry():
                delay = config.delay
                last_exception = None
                for attempt in range(config.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt == 0:
                            logger.warning(f"Request Failed: {e}. Retrying...")
                        else:
                            logger.warning(f"Retry attempt {attempt}/{config.max_retries} failed: {e}")

                        if attempt < config.max_retries:  # Don't sleep after last attempt
                            sleep(delay)
                            if config.backoff:
                                delay *= config.backoff

                # If default_return is None and we have an exception, re-raise it
                if default_return is None and last_exception:
                    raise last_exception
                return default_return

            return _sync_retry()

        return wrapper

    return decorator


class TempPath:
    """Generate temporary file paths"""

    _temp_dir: Optional[str] = None

    @classmethod
    def get_temp_dir(cls) -> str:
        """Get temp directory"""
        if cls._temp_dir is None:
            cls._temp_dir = tempfile.mkdtemp(prefix="atlas_")
        return cls._temp_dir

    @classmethod
    def get_path(cls, ext: str = ".tmp") -> str:
        """Get a temporary file path with given extension"""
        temp_dir = cls.get_temp_dir()
        fd, path = tempfile.mkstemp(suffix=ext, dir=temp_dir)
        os.close(fd)
        return path

    @classmethod
    def cleanup(cls) -> None:
        """Clean up temporary directory"""
        if cls._temp_dir and os.path.exists(cls._temp_dir):
            shutil.rmtree(cls._temp_dir, ignore_errors=True)
            cls._temp_dir = None


def delete_tmp_files(paths: list[Optional[str]]) -> None:
    """Delete temporary files"""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to delete {path}: {e}")


def to_sexagesimal(seconds: float) -> str:
    """Convert seconds to sexagesimal format (HH:MM:SS.mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


class ChunkSlot(BaseModel):
    """Represents a time slot for chunking"""

    start: float
    end: float


class MediaChunk(BaseModel):
    """Represents a media chunk with file path and timing"""

    path: str
    start: float
    end: float


class MediaFileManager:
    """Base class for managing media files with ffmpeg"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._duration: Optional[float] = None
        self._content_type: Optional[str] = None
        self._file_ext: Optional[str] = None
        self.max_workers = min(32, (os.cpu_count() or 1) * 4)

    @property
    def duration(self) -> float:
        """Get media duration in seconds"""
        if self._duration is None:
            self._probe_media()
        return self._duration or 0.0

    @property
    def content_type(self) -> str:
        """Get media content type"""
        if self._content_type is None:
            self._probe_media()
        return self._content_type or "video/mp4"

    @property
    def file_ext(self) -> str:
        """Get file extension"""
        if self._file_ext is None:
            self._file_ext = Path(self.file_path).suffix or ".mp4"
        return self._file_ext

    def _probe_media(self) -> None:
        """Probe media file for metadata"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                self.file_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            data = json.loads(result.stdout)

            # Get duration
            if "format" in data and "duration" in data["format"]:
                self._duration = float(data["format"]["duration"])
            else:
                self._duration = 0.0

            # Determine content type
            streams = data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)

            if has_video:
                self._content_type = "video/mp4"
            elif has_audio:
                self._content_type = "audio/mp3"
            else:
                self._content_type = "application/octet-stream"

        except Exception as e:
            logger.error(f"Error probing media file: {e}")
            self._duration = 0.0
            self._content_type = "video/mp4"

    def _slice_media_file(self, chunk_duration: int, overlap: int = 0) -> list[ChunkSlot]:
        """Slice media file into time slots"""
        duration = self.duration
        if duration <= 0:
            return []

        slots: list[ChunkSlot] = []
        start = 0.0

        while start < duration:
            end = min(start + chunk_duration, duration)
            slots.append(ChunkSlot(start=start, end=end))
            start = end - overlap if overlap > 0 and end < duration else end

        return slots

    async def _clip_media_async(
        self,
        start: float,
        end: float,
        output_path: str,
        use_audio: bool = False,
    ) -> str:
        """Clip media segment asynchronously"""
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            self.file_path,
            "-t",
            str(end - start),
            "-c",
            "copy",
        ]

        if use_audio:
            cmd.extend(["-map", "0:a", "-vn"])
            # Re-encode for audio extraction
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                self.file_path,
                "-t",
                str(end - start),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "64k",
                "-vn",
                output_path,
            ]
        else:
            cmd.append(output_path)

        await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            check=True,
        )
        return output_path


DescriptionAttr = Literal[
    "visual_cues",
    "interactions",
    "contextual_information",
    "audio_analysis",
    "transcript",
]

DEFAULT_DESCRIPTION_ATTRS: list[DescriptionAttr] = [
    "visual_cues",
    "interactions",
    "contextual_information",
    "audio_analysis",
    "transcript",
]


class VideoAttrAnalysis(BaseModel):
    """Video attribute analysis result"""

    attr: DescriptionAttr
    value: str
