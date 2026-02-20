"""
VideoChat — chat history collection (role=user|assistant) per video.

Each chat turn is embedded and stored in the zvec collection for semantic
retrieval, with chronological ordering via timestamp metadata.

Public API
----------
VideoChat.index_message(video_id, role, content)  — embed + store one turn
VideoChat.search(query, video_id, ...)            — semantic retrieval
VideoChat.get_history(video_id, last_n)           — read ordered history from zvec
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from .base import BaseCollection, build_base_vector_schema, make_vector_query
from ..utils import logger

# ---------------------------------------------------------------------------
# Module-level convenience helper
# ---------------------------------------------------------------------------

DEFAULT_STORE_ROOT = Path.home() / ".atlas" / "index"

COLLECTION_NAME = "video_chat"

ChatRole = Literal["user", "assistant"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChatDocument(BaseModel):
    """A single chat message to index in video_chat."""

    id: str
    video_id: str
    role: ChatRole
    content: str
    embedding: List[float]
    metadata: dict[str, Any] = {}


class ChatResult(BaseModel):
    """A document returned by a video_chat semantic query."""

    id: str
    score: float
    video_id: str
    role: ChatRole
    content: str
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# VideoChat
# ---------------------------------------------------------------------------


class VideoChat(BaseCollection):
    """Manages the video_chat zvec collection.

    Owns the zvec collection (semantic embeddings) that stores per-video
    chat history with chronological ordering via timestamp metadata.

    Args:
        col_path: Directory for this collection (e.g. ~/.atlas/index/video_chat).
        embedding_dim: Embedding dimension — 768 or 3072.
    """

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _build_schema(self):
        from zvec import CollectionSchema, DataType, FieldSchema, InvertIndexParam

        return CollectionSchema(
            name=COLLECTION_NAME,
            vectors=[build_base_vector_schema(self.embedding_dim)],
            fields=[
                FieldSchema(
                    "video_id",
                    DataType.STRING,
                    index_param=InvertIndexParam(enable_extended_wildcard=False),
                ),
                # role enables filtering: role == "user" | "assistant"
                FieldSchema(
                    "role",
                    DataType.STRING,
                    index_param=InvertIndexParam(enable_extended_wildcard=False),
                ),
                FieldSchema("content", DataType.STRING),
                FieldSchema("metadata", DataType.STRING),
            ],
        )

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def _make_doc(
        self,
        doc_id: str,
        embedding: List[float],
        video_id: str,
        role: str,
        content: str,
        metadata: Dict,
    ):
        from zvec import Doc

        return Doc(
            id=doc_id,
            vectors={"embedding": embedding},
            fields={
                "video_id": video_id,
                "role": role,
                "content": content,
                "metadata": json.dumps(metadata),
            },
        )

    # ------------------------------------------------------------------
    # Read — chat history
    # ------------------------------------------------------------------

    def get_history(self, video_id: str, last_n=20) -> List[Dict]:
        """Return the *last_n* most recent messages in chronological order.

        Queries the zvec collection filtered by *video_id* and sorts by
        timestamp stored in document metadata.

        Args:
            video_id: The video whose history to retrieve.
            last_n: Maximum number of messages to return.

        Returns:
            List of dicts with keys: role, content, timestamp.
        """
        try:
            results = self.collection.query(
                filter=f"video_id = '{video_id}'",
                topk=min(max(last_n * 10, 200), 1024),
            )
        except Exception as e:
            logger.error(f"Error fetching chat history from zvec: {e}")
            return []

        messages = []
        for r in results:
            meta = json.loads(r.field("metadata"))
            messages.append(
                {
                    "role": r.field("role"),
                    "content": r.field("content"),
                    "timestamp": meta.get("timestamp", ""),
                }
            )

        messages.sort(key=lambda m: m.get("timestamp", ""))
        return messages[-last_n:] if len(messages) > last_n else messages

    # ------------------------------------------------------------------
    # Write — zvec collection
    # ------------------------------------------------------------------

    async def index_message(
        self,
        video_id: str,
        role: ChatRole,
        content: str,
    ) -> str:
        """Embed and store a single chat message in the zvec collection.

        Args:
            video_id: The video this message belongs to.
            role: 'user' or 'assistant'.
            content: Message text.

        Returns:
            Document ID of the inserted message.
        """
        from ..text_embedding import embed_text_async

        embedding = await embed_text_async(content, self.embedding_dim)
        doc_id = self._uuid()
        metadata = {"timestamp": datetime.now().isoformat()}
        zvec_doc = self._make_doc(
            doc_id,
            embedding,
            video_id,
            role,
            content,
            metadata,
        )
        self.collection.insert([zvec_doc])
        self.collection.flush()
        return doc_id

    async def record_turn(
        self,
        video_id: str,
        role: ChatRole,
        content: str,
    ) -> str:
        """Persist a single chat turn to the zvec collection.

        This is the preferred write path — callers (e.g. chat_handler) should
        call this rather than managing index_message separately.

        Returns:
            Document ID of the inserted message.
        """
        return await self.index_message(video_id, role, content)

    # ------------------------------------------------------------------
    # Read — zvec collection
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        video_id: str,
        top_k: int = 5,
        role: Optional[ChatRole] = None,
    ) -> List[ChatResult]:
        """Semantic search in the chat collection for a specific video.

        Args:
            query: Query text.
            video_id: Restrict to this video's chat history.
            top_k: Maximum results.
            role: Optionally restrict to 'user' or 'assistant' messages.

        Returns:
            List of ChatResult ordered by relevance.
        """
        from ..text_embedding import embed_text_async

        query_embedding = await embed_text_async(query, self.embedding_dim)
        try:
            vector_query = make_vector_query(query_embedding)
            filter = f"video_id = '{video_id}' AND role = '{role}'" if role else f"video_id = '{video_id}'"
            results = self.collection.query(
                vector_query,
                topk=top_k,
                filter=filter,
            )
        except Exception as e:
            logger.error(f"Error querying video_chat: {e}")
            return []

        return [
            ChatResult(
                id=r.id,
                score=r.score or 0,
                video_id=r.field("video_id"),  # type: ignore[arg-type]
                role=r.field("role"),  # type: ignore[arg-type]
                content=r.field("content"),  # type: ignore[arg-type]
                metadata=json.loads(r.field("metadata")),  # type: ignore[arg-type]
            )
            for r in results
        ]


def default_video_chat(embedding_dim=768) -> VideoChat:
    """Return a VideoChat object"""
    return VideoChat(
        col_path=DEFAULT_STORE_ROOT / COLLECTION_NAME,
        embedding_dim=embedding_dim,
    )
