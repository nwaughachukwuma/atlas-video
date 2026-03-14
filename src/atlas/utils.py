"""
Core utilities for Atlas
"""

import asyncio
import inspect
import os
import shutil
import tempfile
from dataclasses import dataclass
from functools import wraps
from time import sleep, time
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel

from .logger import logger

T = TypeVar("T")


enable_logging = os.environ.get("ENABLE_LOGGING", False)


def process_time(label: str | None = None, debug=enable_logging):
    """Decorator that records wall-clock execution time per function.

    Timing is accumulated in the global BenchmarkRegistry.  To see the
    per-function breakdown (total / avg / min / max across all calls) pass
    ``--benchmark`` to any CLI command; a rich summary table will be printed
    after the command completes.

    Parameters
    ----------
    label:
        Registry key for this function.  Defaults to the fully-qualified name
        ``"module.ClassName.method_name"``.
    silent: Only record without being noisy
    """

    def decorator(func):
        from .benchmark import registry  # lazy — avoids circular import at module load

        fn_label = label or f"{func.__module__}.{func.__qualname__}"

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                t0 = time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    time_diff = time() - t0
                    registry.record(fn_label, time_diff)
                    if debug:
                        logger.info(f"⏱️ {func.__name__} completed in {time_diff}")

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            t0 = time()
            try:
                return func(*args, **kwargs)
            finally:
                time_diff = time() - t0
                registry.record(fn_label, time_diff)
                if debug:
                    logger.info(f"⏱️ {func.__name__} completed in {time_diff}")

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
        if inspect.iscoroutinefunction(func):

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


DescriptionAttr = Literal[
    "visual_cues",
    "audio_analysis",
    "transcript",
    "interactions",
    "contextual_information",
]

DEFAULT_DESCRIPTION_ATTRS: list[DescriptionAttr] = [
    "visual_cues",
    "audio_analysis",
    "transcript",
    "interactions",
    "contextual_information",
]


class VideoAttrAnalysis(BaseModel):
    """Video attribute analysis result"""

    attr: DescriptionAttr
    value: str
