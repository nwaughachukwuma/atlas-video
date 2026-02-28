"""
Atlas - A multimodal insights engine for video understanding
"""

__version__ = "0.2.1"


# Lazy imports to avoid loading heavy dependencies at import time.
# These are only resolved when actually used (e.g. when a CLI command runs).
def __getattr__(name):
    if name == "TextEmbedding":
        from .text_embedding import TextEmbedding

        return TextEmbedding
    elif name == "VideoIndex":
        from .vector_store import VideoIndex

        return VideoIndex
    elif name == "VideoChat":
        from .vector_store import VideoChat

        return VideoChat
    elif name == "VideoProcessor":
        from .video_processor import VideoProcessor

        return VideoProcessor
    elif name == "VideoProcessorConfig":
        from .video_processor import VideoProcessorConfig

        return VideoProcessorConfig
    elif name == "VideoProcessorResult":
        from .video_processor import VideoProcessorResult

        return VideoProcessorResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
