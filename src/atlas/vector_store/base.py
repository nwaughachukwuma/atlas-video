"""
BaseCollection — shared zvec collection lifecycle and helpers.

Subclasses (VideoIndex, VideoChat) inherit:
  • Lazy collection open/create via the ``collection`` property
  • _uuid(), stats property
  • Module-level zvec factory helpers (_make_vector_query)

Each subclass is responsible for:
  • Defining its own COLLECTION_NAME and schema via _build_schema()
  • Building collection-specific Doc objects via _make_doc()
  • Implementing its domain read/write methods
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from ..uuid import uuid

if TYPE_CHECKING:
    from zvec import Collection, CollectionSchema


_zvec_init_lock = threading.Lock()
_zvec_initialized = False
_collection_lock = threading.Lock()
_collection_cache: dict[str, "Collection"] = {}


# ---------------------------------------------------------------------------
# Module-level zvec factory helpers
# Resolved lazily so the C-extension never loads on --help / import time.
# ---------------------------------------------------------------------------


def get_or_create_collection(path: str, schema: "CollectionSchema") -> "Collection":
    """Open an existing zvec collection or create a new one at *path*."""
    import zvec

    from ..logger import logger

    p = Path(path)
    if not p.exists() or (p.is_dir() and not any(p.iterdir())):
        return zvec.create_and_open(path=path, schema=schema)
    try:
        return zvec.open(path=path)
    except Exception as e:
        logger.warning("Error in zvec.open %s - path: %s", e, path)
        raise RuntimeError(f"Unable to open zvec collection at {path}") from e


def get_shared_collection(path: str, schema: "CollectionSchema") -> "Collection":
    """Return a process-global zvec collection handle for *path*."""
    cached = _collection_cache.get(path)
    if cached is not None:
        return cached

    with _collection_lock:
        cached = _collection_cache.get(path)
        if cached is not None:
            return cached
        _collection_cache[path] = get_or_create_collection(path=path, schema=schema)
        return _collection_cache[path]


def make_vector_query(embedding: List[float]):
    """Build a zvec VectorQuery over the 'embedding' vector field."""
    from zvec import VectorQuery

    return VectorQuery("embedding", vector=embedding)


def build_base_vector_schema(embedding_dim: int):
    """Return the common VectorSchema used by every collection."""
    from zvec import DataType, HnswIndexParam, MetricType, VectorSchema

    return VectorSchema(
        name="embedding",
        data_type=DataType.VECTOR_FP32,
        dimension=embedding_dim,
        index_param=HnswIndexParam(metric_type=MetricType.COSINE),
    )


# ---------------------------------------------------------------------------
# BaseCollection
# ---------------------------------------------------------------------------


class BaseCollection(ABC):
    """Abstract base for zvec-backed collection wrappers.

    Subclasses must implement ``_build_schema`` to return the
    zvec CollectionSchema appropriate for their collection.

    Args:
        col_path: Directory path for this collection.
        embedding_dim: Embedding dimension — 768 or 3072.
    """

    def __init__(self, col_path: Path, embedding_dim=768) -> None:
        self.col_path = col_path
        self.embedding_dim = embedding_dim
        self._collection: Optional["Collection"] = None
        self._init_zvec()

    def _init_zvec(self):
        global _zvec_initialized

        if _zvec_initialized:
            return

        import zvec

        with _zvec_init_lock:
            if not _zvec_initialized:
                zvec.init(
                    log_type=zvec.LogType.CONSOLE,
                    log_level=zvec.LogLevel.WARN,
                    query_threads=4,
                )
                _zvec_initialized = True

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_schema(self) -> "CollectionSchema":
        """Return the zvec CollectionSchema for this collection."""

    # ------------------------------------------------------------------
    # Lazy collection lifecycle
    # ------------------------------------------------------------------

    @property
    def collection(self) -> "Collection":
        """Lazily open or create the zvec collection on first access."""
        if self._collection is None:
            self.col_path.parent.mkdir(parents=True, exist_ok=True)
            self._collection = get_shared_collection(
                str(self.col_path),
                self._build_schema(),
            )
        return self._collection

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    def _uuid(self) -> str:
        """Generate a random 16-character document ID."""
        return uuid(16)

    @property
    def stats(self) -> Any:
        """Raw zvec collection stats."""
        return self.collection.stats
