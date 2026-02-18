"""
VideoIndex — multimodal insights collection (one doc per video segment).

Each document embeds the full concatenated analysis string for a segment,
plus granular per-attribute documents, enabling both broad and targeted
semantic retrieval.

Module-level helpers
--------------------
index_video(video_path, ...)   — process + embed + register a video file
search_video(query, ...)       — semantic search over indexed segments
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from pydantic import BaseModel

from .base import BaseCollection, build_base_vector_schema, make_vector_query
from ..utils import logger
from ..uuid import uuid

if TYPE_CHECKING:
    from ..video_processor import VideoDescription, VideoProcessorResult


COLLECTION_NAME = "video_index"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class IndexDocument(BaseModel):
    """A single document to index in video_index."""

    id: str
    video_id: str
    start: float
    end: float
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = {}


class SearchResult(BaseModel):
    """A document returned by a video_index query."""

    id: str
    score: float
    video_id: str
    start: float
    end: float
    content: str
    metadata: dict[str, Any] = {}


class VideoEntry(BaseModel):
    """Lightweight registry entry for an indexed video."""

    video_id: str
    indexed_at: str


# ---------------------------------------------------------------------------
# VideoIndex
# ---------------------------------------------------------------------------


class VideoIndex(BaseCollection):
    """Manages the video_index zvec collection.

    Owns both the zvec collection (embeddings + metadata) and the JSON
    registry sidecar that tracks which video_ids have been indexed.

    Args:
        index_path: Directory for this collection (e.g. ~/.atlas/index/video_index).
        embedding_dim: Embedding dimension — 768 or 3072.
    """

    # Registry lives inside the collection directory
    @property
    def _registry_path(self) -> Path:
        return self.index_path / "registry.json"

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _build_schema(self):
        from zvec import CollectionSchema, DataType, FieldSchema, InvertIndexParam

        return CollectionSchema(
            name=COLLECTION_NAME,
            vectors=build_base_vector_schema(self.embedding_dim),
            fields=[
                FieldSchema(
                    "video_id",
                    DataType.STRING,
                    index_param=InvertIndexParam(enable_extended_wildcard=False),
                ),
                FieldSchema("start", DataType.FLOAT),
                FieldSchema("end", DataType.FLOAT),
                FieldSchema("content", DataType.STRING),
                FieldSchema("metadata", DataType.STRING),
            ],
        )

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def _create_searchable_content(self, description: "VideoDescription") -> str:
        """Concatenate all analysis attribute values into a single searchable string."""
        parts = []
        for analysis in description.video_analysis:
            attr_name = " ".join(analysis.attr.upper().split("_"))
            parts.append(f"{attr_name}: {analysis.value}")
        return "\n".join(parts)

    def _make_doc(
        self,
        doc_id: str,
        embedding: list,
        video_id: str,
        start: float,
        end: float,
        content: str,
        metadata: dict,
    ):
        from zvec import Doc

        return Doc(
            id=doc_id,
            vectors={"embedding": embedding},
            fields={
                "video_id": video_id,
                "start": start,
                "end": end,
                "content": content,
                "metadata": json.dumps(metadata),
            },
        )

    # ------------------------------------------------------------------
    # Registry sidecar
    # ------------------------------------------------------------------

    def list_videos(self) -> List[VideoEntry]:
        """Return all registered videos from the registry sidecar."""
        if not self._registry_path.exists():
            return []
        try:
            data = json.loads(self._registry_path.read_text())
            return [VideoEntry(**v) for v in data]
        except Exception as e:
            logger.error(f"Error reading video registry: {e}")
            return []

    def register(self, video_id: str) -> None:
        """Add *video_id* to the registry (no-op if already present)."""
        entries: list[dict] = []
        if self._registry_path.exists():
            try:
                entries = json.loads(self._registry_path.read_text())
            except Exception:
                entries = []
        if video_id not in {e["video_id"] for e in entries}:
            entries.append({"video_id": video_id, "indexed_at": datetime.now().isoformat()})
            self._registry_path.write_text(json.dumps(entries, indent=2))

    def unregister(self, video_id: str) -> None:
        """Remove *video_id* from the registry."""
        if not self._registry_path.exists():
            return
        try:
            entries = json.loads(self._registry_path.read_text())
            updated = [e for e in entries if e.get("video_id") != video_id]
            if len(updated) != len(entries):
                self._registry_path.write_text(json.dumps(updated, indent=2))
        except Exception as e:
            logger.error(f"Error unregistering video_id={video_id}: {e}")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def index_video_result(
        self,
        result: "VideoProcessorResult",
        video_id: str,
        batch_size: int = 10,
    ) -> int:
        """Embed and insert all segments from a VideoProcessorResult.

        Args:
            result: Output of VideoProcessor.
            video_id: Stable identifier assigned to this video.
            batch_size: Number of docs per zvec insert call.

        Returns:
            Total number of documents inserted.
        """
        from ..text_embedding import embed_text_async

        documents: list[IndexDocument] = []

        for desc in result.video_descriptions:
            content = self._create_searchable_content(desc)
            if not content.strip():
                continue

            embedding = await embed_text_async(content, self.embedding_dim)
            documents.append(
                IndexDocument(
                    id=self._new_id(),
                    video_id=video_id,
                    start=desc.start,
                    end=desc.end,
                    content=content,
                    embedding=embedding,
                    metadata={
                        "duration": desc.end - desc.start,
                        "indexed_at": datetime.now().isoformat(),
                    },
                )
            )

            # Granular per-attribute documents for targeted retrieval
            for analysis in desc.video_analysis:
                if not analysis.value.strip():
                    continue
                analysis_embedding = await embed_text_async(analysis.value, self.embedding_dim)
                documents.append(
                    IndexDocument(
                        id=self._new_id(),
                        video_id=video_id,
                        start=desc.start,
                        end=desc.end,
                        content=f"{analysis.attr}: {analysis.value}",
                        embedding=analysis_embedding,
                        metadata={
                            "attr": analysis.attr,
                            "duration": desc.end - desc.start,
                            "indexed_at": datetime.now().isoformat(),
                        },
                    )
                )

        indexed = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            zvec_docs = [
                self._make_doc(d.id, d.embedding, d.video_id, d.start, d.end, d.content, d.metadata) for d in batch
            ]
            self.collection.insert(zvec_docs)
            indexed += len(zvec_docs)

        logger.info(f"Indexed {indexed} documents for video_id={video_id}")
        self.collection.flush()
        self.collection.optimize()
        return indexed

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 10,
        video_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Semantic search over video segments.

        Args:
            query: Natural-language query.
            top_k: Maximum results to return.
            video_id: When provided, restrict results to this video.

        Returns:
            List of SearchResult ordered by relevance.
        """
        from ..text_embedding import embed_text_async

        query_embedding = await embed_text_async(query, self.embedding_dim)
        try:
            vector_query = make_vector_query(query_embedding)
            if video_id:
                results = self.collection.query(
                    vector_query,
                    topk=top_k,
                    filter=f"video_id == {video_id}",
                )
            else:
                results = self.collection.query(vector_query, topk=top_k)
        except Exception as e:
            logger.error(f"Error querying video_index: {e}")
            return []

        return [
            SearchResult(
                id=r.id,
                score=r.score or 0,
                video_id=r.field("video_id"),  # type: ignore[arg-type]
                start=r.field("start"),  # type: ignore[arg-type]
                end=r.field("end"),  # type: ignore[arg-type]
                content=r.field("content"),  # type: ignore[arg-type]
                metadata=json.loads(r.field("metadata")),  # type: ignore[arg-type]
            )
            for r in results
        ]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_by_video(self, video_id: str) -> None:
        """Delete all documents and registry entry for *video_id*."""
        try:
            self.collection.delete_by_filter(filter=f"video_id == {video_id}")
        except Exception as e:
            logger.error(f"Error deleting video_index docs for video_id={video_id}: {e}")
        self.unregister(video_id)

    def delete(self, doc_id: str) -> None:
        """Delete a single document by ID."""
        try:
            self.collection.delete(ids=doc_id)
        except Exception as e:
            logger.error(f"Error deleting video_index doc {doc_id}: {e}")


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

DEFAULT_STORE_ROOT = Path.home() / ".atlas" / "index"


def default_video_index(store_path: Optional[str] = None, embedding_dim: int = 768) -> VideoIndex:
    """Return a VideoIndex pointed at *store_path*/video_index (or the default root)."""
    root = Path(store_path) if store_path else DEFAULT_STORE_ROOT
    return VideoIndex(index_path=root / "video_index", embedding_dim=embedding_dim)


async def index_video(
    video_path: str,
    chunk_duration: int = 10,
    overlap: int = 0,
    store_path: Optional[str] = None,
    embedding_dim: int = 768,
) -> tuple[str, int, "VideoProcessorResult"]:
    """Process a video file, index it, and register it.

    Args:
        video_path: Path to the video file.
        chunk_duration: Chunk duration in seconds.
        overlap: Overlap between chunks in seconds.
        store_path: Directory for the video_index collection.
        embedding_dim: Embedding dimension (768 or 3072).

    Returns:
        (video_id, number_of_docs_indexed, VideoProcessorResult)
    """
    from ..video_processor import VideoProcessor, VideoProcessorConfig

    config = VideoProcessorConfig(
        video_path=video_path,
        chunk_duration=chunk_duration,
        overlap=overlap,
    )
    async with VideoProcessor(config) as processor:
        result = await processor.process()

    vi = default_video_index(store_path, embedding_dim)
    video_id = uuid(16)
    vi.index_path.mkdir(parents=True, exist_ok=True)
    indexed = await vi.index_video_result(result, video_id=video_id)
    vi.register(video_id)
    return video_id, indexed, result


async def search_video(
    query: str,
    top_k: int = 10,
    video_id: Optional[str] = None,
    store_path: Optional[str] = None,
    embedding_dim: int = 768,
) -> List[SearchResult]:
    """Semantic search over indexed video segments.

    Args:
        query: Natural-language query.
        top_k: Number of results.
        video_id: Restrict to this video (optional).
        store_path: Directory for the video_index collection.
        embedding_dim: Embedding dimension (768 or 3072).

    Returns:
        List of SearchResult ordered by relevance.
    """
    vi = default_video_index(store_path, embedding_dim)
    return await vi.search(query, top_k=top_k, video_id=video_id)
