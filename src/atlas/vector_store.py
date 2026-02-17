"""
Vector store using zvec for local vector search
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import zvec
from pydantic import BaseModel

from atlas.text_embedding import embed_text_async
from atlas.utils import logger
from atlas.video_processor import VideoDescription, VideoProcessorResult


class IndexDocument(BaseModel):
    """Document to index in vector store"""

    id: str
    video_path: str
    start: float
    end: float
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = {}


class SearchResult(BaseModel):
    """Search result from vector store"""

    id: str
    score: float
    video_path: str
    start: float
    end: float
    content: str
    metadata: dict[str, Any] = {}


class VectorStore:
    """Local vector store using zvec"""

    DEFAULT_EMBEDDING_DIM = 768
    COLLECTION_NAME = "atlas_video_index"

    def __init__(self, store_path: Optional[str] = None, embedding_dim: int = DEFAULT_EMBEDDING_DIM):
        """Initialize vector store

        Args:
            store_path: Path to store the vector index. Defaults to ~/.atlas/index
            embedding_dim: Dimension of embeddings (768 or 3072 for Gemini)
        """
        self.store_path = Path(store_path or Path.home() / ".atlas" / "index")
        self.embedding_dim = embedding_dim
        self._collection: Optional[Any] = None

    @property
    def collection(self):
        """Get or create the zvec collection"""
        if self._collection is None:
            self._ensure_store_path()
            self._collection = self._create_or_open_collection()
        return self._collection

    def _ensure_store_path(self) -> None:
        """Ensure store directory exists"""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _create_or_open_collection(self):
        """Create or open zvec collection"""
        schema = zvec.CollectionSchema(
            name=self.COLLECTION_NAME,
            vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, self.embedding_dim),
        )

        if self.store_path.exists():
            try:
                return zvec.open_collection(path=str(self.store_path))
            except Exception:
                # If opening fails, create new
                pass

        return zvec.create_and_open(path=str(self.store_path), schema=schema)

    def _create_document_id(self, video_path: str, start: float, end: float, attr: str) -> str:
        """Create a unique document ID"""
        # Create a hash-like ID from video path and timing
        import hashlib

        content = f"{video_path}:{start}:{end}:{attr}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _create_searchable_content(self, description: VideoDescription) -> str:
        """Create searchable content from video description"""
        parts = []
        for analysis in description.video_analysis:
            attr_name = " ".join(analysis.attr.upper().split("_"))
            parts.append(f"{attr_name}: {analysis.value}")
        return "\n".join(parts)

    async def index_video_result(
        self,
        result: VideoProcessorResult,
        batch_size: int = 10,
    ) -> int:
        """Index video processor result

        Args:
            result: VideoProcessorResult from video processing
            batch_size: Number of documents to index at once

        Returns:
            Number of documents indexed
        """
        documents: list[IndexDocument] = []
        video_path = result.video_path

        for desc in result.video_descriptions:
            # Create a combined document for the entire segment
            content = self._create_searchable_content(desc)
            if not content.strip():
                continue

            # Get embedding for content
            try:
                embedding = await embed_text_async(content, self.embedding_dim)
            except Exception as e:
                logger.error(f"Error getting embedding for segment {desc.start}-{desc.end}: {e}")
                continue

            doc_id = self._create_document_id(video_path, desc.start, desc.end, "combined")
            doc = IndexDocument(
                id=doc_id,
                video_path=video_path,
                start=desc.start,
                end=desc.end,
                content=content,
                embedding=embedding,
                metadata={
                    "duration": desc.end - desc.start,
                    "indexed_at": datetime.now().isoformat(),
                },
            )
            documents.append(doc)

            # Also create individual documents for each analysis type
            for analysis in desc.video_analysis:
                if not analysis.value.strip():
                    continue

                try:
                    analysis_embedding = await embed_text_async(analysis.value, self.embedding_dim)
                except Exception as e:
                    logger.error(f"Error getting embedding for {analysis.attr}: {e}")
                    continue

                analysis_doc_id = self._create_document_id(video_path, desc.start, desc.end, analysis.attr)
                analysis_doc = IndexDocument(
                    id=analysis_doc_id,
                    video_path=video_path,
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
                documents.append(analysis_doc)

        # Insert documents in batches
        indexed = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            zvec_docs = [
                zvec.Doc(
                    id=doc.id,
                    vectors={"embedding": doc.embedding},
                    metadata={
                        "video_path": doc.video_path,
                        "start": doc.start,
                        "end": doc.end,
                        "content": doc.content,
                        **doc.metadata,
                    },
                )
                for doc in batch
            ]
            try:
                self.collection.insert(zvec_docs)
                indexed += len(zvec_docs)
            except Exception as e:
                logger.error(f"Error inserting batch: {e}")

        logger.info(f"Indexed {indexed} documents for {video_path}")
        return indexed

    async def search(
        self,
        query: str,
        top_k: int = 10,
        video_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """Search for similar content

        Args:
            query: Query text
            top_k: Number of results to return
            video_filter: Optional video path to filter results

        Returns:
            List of search results
        """
        # Get embedding for query
        try:
            query_embedding = await embed_text_async(query, self.embedding_dim)
        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            return []

        # Build query
        vector_query = zvec.VectorQuery("embedding", vector=query_embedding)

        try:
            results = self.collection.query(vector_query, topk=top_k)
        except Exception as e:
            logger.error(f"Error querying collection: {e}")
            return []

        # Convert results
        search_results = []
        for result in results:
            metadata = result.get("metadata", {})

            # Apply video filter if specified
            if video_filter and metadata.get("video_path") != video_filter:
                continue

            search_result = SearchResult(
                id=result["id"],
                score=result["score"],
                video_path=metadata.get("video_path", ""),
                start=metadata.get("start", 0.0),
                end=metadata.get("end", 0.0),
                content=metadata.get("content", ""),
                metadata=metadata,
            )
            search_results.append(search_result)

        return search_results

    def delete_by_video(self, video_path: str) -> int:
        """Delete all documents for a video

        Args:
            video_path: Path of video to delete documents for

        Returns:
            Number of documents deleted
        """
        # Note: zvec may not have direct delete by metadata, so we need to find and delete
        # This implementation depends on zvec's API capabilities
        try:
            # Search for all documents with this video path
            # Since zvec might not support metadata filtering in search,
            # we might need to maintain a separate index
            logger.info(f"Deleting documents for {video_path}")
            # For now, we'll note that this functionality depends on zvec's delete API
            return 0
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the vector store"""
        try:
            # Get collection stats
            return {
                "store_path": str(self.store_path),
                "embedding_dim": self.embedding_dim,
                "collection_name": self.COLLECTION_NAME,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}


async def index_video(
    video_path: str,
    chunk_duration: int = 10,
    overlap: int = 0,
    store_path: Optional[str] = None,
) -> tuple[int, VideoProcessorResult]:
    """Process and index a video

    Args:
        video_path: Path to the video file
        chunk_duration: Duration of each chunk in seconds
        overlap: Overlap between chunks in seconds
        store_path: Path to store the vector index

    Returns:
        Tuple of (number of documents indexed, processing result)
    """
    from atlas.video_processor import VideoProcessor, VideoProcessorConfig

    config = VideoProcessorConfig(
        video_path=video_path,
        chunk_duration=chunk_duration,
        overlap=overlap,
    )

    async with VideoProcessor(config) as processor:
        result = await processor.process()

    store = VectorStore(store_path=store_path)
    indexed = await store.index_video_result(result)

    return indexed, result


async def search_video(
    query: str,
    top_k: int = 10,
    video_filter: Optional[str] = None,
    store_path: Optional[str] = None,
) -> list[SearchResult]:
    """Search indexed videos

    Args:
        query: Query text
        top_k: Number of results to return
        video_filter: Optional video path to filter results
        store_path: Path to the vector index

    Returns:
        List of search results
    """
    store = VectorStore(store_path=store_path)
    return await store.search(query, top_k=top_k, video_filter=video_filter)
