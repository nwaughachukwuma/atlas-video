"""
Atlas - A multimodal insights engine for video understanding
"""

__version__ = "0.1.0"

from .text_embedding import TextEmbedding
from .vector_store import VectorStore
from .video_processor import VideoProcessor, VideoProcessorConfig, VideoProcessorResult

__all__ = [
    "VideoProcessor",
    "VideoProcessorConfig",
    "VideoProcessorResult",
    "TextEmbedding",
    "VectorStore",
]
