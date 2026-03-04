"""
VideoIndex — multimodal insights collection (one doc per video segment).

Each document embeds the full concatenated analysis string for a segment,
plus granular per-attribute documents, enabling both broad and targeted
semantic retrieval.

Module-level helpers
--------------------
index_video(video_path, ...)   — process + embed + index a video file
search_video(query, ...)       — semantic search over indexed segments
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from pydantic import BaseModel

from .base import BaseCollection, build_base_vector_schema, make_vector_query
from ..utils import DEFAULT_DESCRIPTION_ATTRS, DescriptionAttr, logger
from ..uuid import uuid

if TYPE_CHECKING:
    from ..video_processor import VideoDescription, VideoProcessorResult


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

DEFAULT_STORE_ROOT = Path(os.environ.get("ATLAS_HOME", Path.home() / ".atlas")) / "index"
COLLECTION_NAME = "video_index"
DEFAULT_EMBEDDING_CONCURRENCY = 10


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
    embedding: List[float]
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

    Owns the zvec collection (embeddings + metadata) that stores
    multimodal segment data and tracks which video_ids have been indexed.

    Args:
        col_path: Directory for this collection (e.g. ~/.atlas/index/video_index).
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
        embedding: List[float],
        video_id: str,
        start: float,
        end: float,
        content: str,
        metadata: Dict,
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
    # Read helpers
    # ------------------------------------------------------------------

    def list_videos(self) -> List[VideoEntry]:
        """Return all indexed videos by scanning the zvec collection."""
        try:
            results = self.collection.query(filter="video_id is not null", topk=1_000)
        except Exception as e:
            logger.error(f"Error listing videos from zvec: {e}")
            return []

        videos: dict[str, str] = {}  # video_id → earliest indexed_at
        for r in results:
            vid = r.field("video_id")
            meta = json.loads(r.field("metadata"))
            ts = meta.get("indexed_at", "")
            if vid not in videos or (ts and ts < videos[vid]):
                videos[vid] = ts

        return sorted(
            [VideoEntry(video_id=vid, indexed_at=ts) for vid, ts in videos.items()],
            key=lambda e: e.indexed_at,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def index_video_result(
        self,
        result: "VideoProcessorResult",
        video_id: str,
        batch_size=10,
    ) -> int:
        """Embed and insert all segments from a VideoProcessorResult.

        Args:
            result: Output of VideoProcessor.
            video_id: Stable identifier assigned to this video.
            batch_size: Number of docs per zvec insert call.

        Returns:
            Total number of documents inserted.
        """
        from ..text_embedding import embed_text

        def _make_index_doc(
            desc: VideoDescription,
            content: str,
            embedding: List[float],
            attr: Optional[DescriptionAttr] = None,
        ) -> IndexDocument:
            metadata = {
                "duration": desc.end - desc.start,
                "indexed_at": datetime.now().isoformat(),
            }
            if attr:
                metadata["attr"] = attr
            return IndexDocument(
                id=self._uuid(),
                video_id=video_id,
                start=desc.start,
                end=desc.end,
                content=content,
                embedding=embedding,
                metadata=metadata,
            )

        semaphore = asyncio.Semaphore(DEFAULT_EMBEDDING_CONCURRENCY)

        async def _guarded_embed(content: str) -> List[float]:
            async with semaphore:
                return await embed_text(content, self.embedding_dim)

        async def _embed_description(desc: VideoDescription):
            content = self._create_searchable_content(desc).strip()
            embedding = await _guarded_embed(content)
            docs = [_make_index_doc(desc, content, embedding)]

            # Persist summary in main document metadata for later retrieval
            if desc.summary:
                docs[0].metadata["summary"] = desc.summary

            # Granular per-attribute documents for targeted retrieval
            analysis_items = [a for a in desc.video_analysis if a.value.strip()]
            analysis_embeddings = await asyncio.gather(*[_guarded_embed(a.value) for a in analysis_items])
            docs.extend(
                _make_index_doc(desc, f"{a.attr}: {a.value}", emb, a.attr)
                for a, emb in zip(analysis_items, analysis_embeddings)
            )
            return docs

        descriptions = [d for d in result.video_descriptions if self._create_searchable_content(d).strip()]
        results = await asyncio.gather(*[_embed_description(d) for d in descriptions])
        documents = [doc for res in results for doc in res]

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            self.collection.insert(
                [self._make_doc(d.id, d.embedding, d.video_id, d.start, d.end, d.content, d.metadata) for d in batch]
            )

        self.collection.flush()
        self.collection.optimize()
        indexed = len(documents)
        logger.info(f"Indexed {indexed} documents for video_id={video_id}")

        return indexed

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k=10,
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
        from ..text_embedding import embed_text

        query_embedding = await embed_text(query, self.embedding_dim)
        try:
            vector_query = make_vector_query(query_embedding)
            if video_id:
                results = self.collection.query(
                    vector_query,
                    topk=top_k,
                    filter=f"video_id = '{video_id}'",
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

    def get_video_data(self, video_id: str) -> Optional[dict]:
        """Retrieve all indexed data for *video_id* in extract-command shape.

        Returns a dict with keys: video_id, duration, video_descriptions,
        segments_count — or ``None`` if the video is not found.
        """
        try:
            results = self.collection.query(topk=1024, filter=f"video_id = '{video_id}'")
            if not results:
                return None
        except Exception as e:
            logger.error(f"Error fetching video data: {e}")
            return None

        # Group results by (start, end) to reconstruct segments
        segments: dict[tuple[float, float], dict] = {}
        for r in results:
            start = float(r.field("start"))
            end = float(r.field("end"))
            meta = json.loads(r.field("metadata"))
            key = (start, end)

            if key not in segments:
                segments[key] = {
                    "start": start,
                    "end": end,
                    "summary": None,
                    "video_analysis": [],
                }

            if "attr" in meta:
                # Per-attribute document
                content = r.field("content")
                attr = meta["attr"]
                prefix = f"{attr}: "
                value = content[len(prefix) :] if content.startswith(prefix) else content
                segments[key]["video_analysis"].append({"attr": attr, "value": value})
            elif "summary" in meta:
                # Main document with summary
                segments[key]["summary"] = meta["summary"]

        sorted_segments = sorted(segments.values(), key=lambda s: s["start"])
        duration = max(s["end"] for s in sorted_segments) if sorted_segments else 0
        return {
            "video_id": video_id,
            "duration": duration,
            "video_descriptions": sorted_segments,
            "segments_count": len(sorted_segments),
        }

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_by_video(self, video_id: str) -> None:
        """Delete all documents for *video_id*."""
        try:
            self.collection.delete_by_filter(filter=f"video_id = '{video_id}'")
        except Exception as e:
            logger.error(f"Error deleting video_index docs for video_id={video_id}: {e}")

    def delete(self, doc_id: str) -> None:
        """Delete a single document by ID."""
        try:
            self.collection.delete(ids=doc_id)
        except Exception as e:
            logger.error(f"Error deleting video_index doc {doc_id}: {e}")


def default_video_index(embedding_dim: int = 768) -> VideoIndex:
    """Return a VideoIndex object"""
    return VideoIndex(
        col_path=DEFAULT_STORE_ROOT / COLLECTION_NAME,
        embedding_dim=embedding_dim,
    )


async def index_video(
    video_path: str,
    chunk_duration=15,
    overlap=1,
    description_attrs: Optional[List[DescriptionAttr]] = None,
    include_summary=True,
    embedding_dim=768,
    on_segment: Optional[Callable[[VideoDescription], None]] = None,
) -> tuple[str, int, "VideoProcessorResult"]:
    """Process a video file, index it, and register it.

    Args:
        video_path: Path to the video file.
        chunk_duration: Chunk duration in seconds.
        overlap: Overlap between chunks in seconds.
        description_attrs: List of attributes to extract (e.g., ["visual_cues", "interactions"]).
        include_summary: Whether to generate summaries for each segment.
        embedding_dim: Embedding dimension (768 or 3072).

    Returns:
        (video_id, number_of_docs_indexed, VideoProcessorResult)
    """
    from ..video_processor import VideoProcessor, VideoProcessorConfig

    attrs = description_attrs if description_attrs else DEFAULT_DESCRIPTION_ATTRS

    config = VideoProcessorConfig(
        video_path=video_path,
        chunk_duration=chunk_duration,
        overlap=overlap,
        description_attrs=attrs,
        include_summary=include_summary,
    )
    async with VideoProcessor(config) as processor:
        result = await processor.process(on_segment)

    vi = default_video_index(embedding_dim)
    vi.col_path.mkdir(parents=True, exist_ok=True)

    video_id = uuid(16)
    indexed = await vi.index_video_result(result, video_id=video_id)

    return video_id, indexed, result


async def search_video(
    query: str,
    top_k: int = 10,
    video_id: Optional[str] = None,
    embedding_dim: int = 768,
) -> List[SearchResult]:
    """Semantic search over indexed video segments.

    Args:
        query: Natural-language query.
        top_k: Number of results.
        video_id: Restrict to this video (optional).
        embedding_dim: Embedding dimension (768 or 3072).

    Returns:
        List of SearchResult ordered by relevance.
    """
    vi = default_video_index(embedding_dim)
    return await vi.search(query, top_k, video_id)
