"""
Atlas Media Manager Module
"""

import asyncio
import json
import os
import subprocess
from typing import Optional

from .file_extension import get_content_type, get_file_extension
from .logger import logger
from .settings import settings
from .utils import ChunkSlot, TempPath, process_time


class MediaFileManager:
    """Base class for managing media files with ffmpeg"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._duration: Optional[float] = None
        self._content_type: Optional[str] = None

        self._file_ext: Optional[str] = None
        self.max_workers = min(settings.process_workers, (os.cpu_count() or 1) * 4)

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
            self._content_type = get_content_type(self.file_path)
        return self._content_type

    @property
    def file_ext(self) -> str:
        """Get file extension"""
        if self._file_ext is None:
            self._file_ext = get_file_extension(self.file_path)
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

        except FileNotFoundError as e:
            if e.filename in ("ffprobe", "ffmpeg"):
                raise RuntimeError("ffmpeg/ffprobe not found — please install ffmpeg") from e
            raise e
        except Exception as e:
            logger.error(f"Error probing media file: {e}")
            raise e

    def _slice_media_file(self, chunk_duration: int, overlap: int = 0) -> list[ChunkSlot]:
        """Slice media file into time slots"""
        duration = self.duration
        if duration <= 0:
            raise RuntimeError(f"Media file '{self.file_path}' has unknown duration. Ensure the file is a valid video.")

        slots: list[ChunkSlot] = []
        start = 0.0

        while start < duration:
            end = min(start + chunk_duration, duration)
            slots.append(ChunkSlot(start=start, end=end))
            start = end - overlap if overlap > 0 and end < duration else end

        return slots

    @process_time()
    async def _clip_media_async(
        self,
        start: float,
        end: float,
        output_path: str,
        use_audio=False,
    ) -> str:
        """Clip media segment asynchronously.

        For audio extraction we resample to 16 kHz mono (what Whisper expects).
        """
        store_as_audio = use_audio and self.content_type.startswith("video")
        if store_as_audio:
            output_path = TempPath().get_path(ext=".wav")
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                self.file_path,
                "-t",
                str(end - start),
                "-map",
                "0:a:0",  # select first audio track directly
                "-vn",
                "-ar",
                "16000",  # 16 kHz — optimal for Whisper
                "-ac",
                "1",  # mono
                "-c:a",
                "pcm_s16le",  # raw PCM — trivial to encode, no compression overhead
                "-avoid_negative_ts",
                "make_zero",
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                self.file_path,
                "-t",
                str(end - start),
                "-c",
                "copy",
                output_path,
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return output_path

        err_text = (stderr or b"").decode(errors="replace").strip()
        logger.error(
            "ffmpeg failed (rc=%d) for %s [%s\u2013%s]: %s",
            proc.returncode,
            self.file_path,
            start,
            end,
            err_text or "(no stderr)",
        )
        raise subprocess.CalledProcessError(proc.returncode or 1, cmd[0], stdout, stderr)
