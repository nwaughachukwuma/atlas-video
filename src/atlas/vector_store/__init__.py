"""
atlas.vector_store — vector index package for Atlas.

Structure
---------
base.py        BaseCollection — shared zvec lifecycle and helpers
video_index.py VideoIndex     — multimodal segment embeddings
video_chat.py  VideoChat      — per-video chat history embeddings

All public symbols are re-exported here so callers can use either:
    from atlas.vector_store import VideoIndex, SearchResult
    from atlas.vector_store.video_index import VideoIndex, index_video
"""

from .video_chat import (
    COLLECTION_NAME as CHAT_COLLECTION_NAME,
)
from .video_chat import (
    ChatDocument,
    ChatResult,
    ChatRole,
    VideoChat,
)
from .video_index import (
    COLLECTION_NAME as VIDEO_COLLECTION_NAME,
)
from .video_index import (
    IndexDocument,
    SearchResult,
    VideoEntry,
    VideoIndex,
    index_video,
    search_video,
)

__all__ = [
    # video_index
    "VideoIndex",
    "IndexDocument",
    "SearchResult",
    "VideoEntry",
    "index_video",
    "search_video",
    # video_chat
    "VideoChat",
    "ChatDocument",
    "ChatResult",
    "ChatRole",
    # collection name constants
    "VIDEO_COLLECTION_NAME",
    "CHAT_COLLECTION_NAME",
]
