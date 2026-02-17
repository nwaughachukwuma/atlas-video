"""
Unit tests for atlas.vector_store module
"""

from src.atlas.utils import VideoAttrAnalysis
from src.atlas.vector_store import (
    IndexDocument,
    SearchResult,
    VectorStore,
)
from src.atlas.video_processor import VideoDescription


class TestIndexDocument:
    """Tests for IndexDocument model"""

    def test_creates_document(self):
        """Test IndexDocument creation"""
        doc = IndexDocument(
            id="doc123",
            video_path="/tmp/video.mp4",
            start=0.0,
            end=10.0,
            content="Test content",
            embedding=[0.1] * 768,
        )
        assert doc.id == "doc123"
        assert doc.video_path == "/tmp/video.mp4"
        assert doc.start == 0.0
        assert doc.end == 10.0
        assert doc.content == "Test content"
        assert len(doc.embedding) == 768

    def test_with_metadata(self):
        """Test IndexDocument with metadata"""
        doc = IndexDocument(
            id="doc123",
            video_path="/tmp/video.mp4",
            start=0.0,
            end=10.0,
            content="Test content",
            embedding=[0.1] * 768,
            metadata={"attr": "visual_cues"},
        )
        assert doc.metadata == {"attr": "visual_cues"}


class TestSearchResult:
    """Tests for SearchResult model"""

    def test_creates_result(self):
        """Test SearchResult creation"""
        result = SearchResult(
            id="doc123",
            score=0.95,
            video_path="/tmp/video.mp4",
            start=0.0,
            end=10.0,
            content="Test content",
        )
        assert result.id == "doc123"
        assert result.score == 0.95
        assert result.video_path == "/tmp/video.mp4"
        assert result.start == 0.0
        assert result.end == 10.0
        assert result.content == "Test content"

    def test_with_metadata(self):
        """Test SearchResult with metadata"""
        result = SearchResult(
            id="doc123",
            score=0.95,
            video_path="/tmp/video.mp4",
            start=0.0,
            end=10.0,
            content="Test content",
            metadata={"attr": "visual_cues"},
        )
        assert result.metadata == {"attr": "visual_cues"}


class TestVectorStore:
    """Tests for VectorStore class"""

    def test_default_initialization(self, tmp_path):
        """Test VectorStore default initialization"""
        store = VectorStore()
        assert store.embedding_dim == 768
        assert ".atlas" in str(store.store_path)

    def test_custom_initialization(self, tmp_path):
        """Test VectorStore with custom path"""
        custom_path = tmp_path / "custom_store"
        store = VectorStore(store_path=str(custom_path), embedding_dim=3072)
        assert store.embedding_dim == 3072
        assert store.store_path == custom_path

    def test_doc_id(self):
        """Test document ID creation"""
        store = VectorStore()
        assert len(store._doc_id()) == 16

    def test_create_searchable_content(self):
        """Test searchable content creation"""
        store = VectorStore()
        analysis1 = VideoAttrAnalysis(attr="visual_cues", value="A person walking")
        analysis2 = VideoAttrAnalysis(attr="audio_analysis", value="Background music")
        desc = VideoDescription(
            start=0.0,
            end=10.0,
            video_analysis=[analysis1, analysis2],
        )
        content = store._create_searchable_content(desc)
        assert "VISUAL CUES: A person walking" in content
        assert "AUDIO ANALYSIS: Background music" in content

    def test_get_stats(self, tmp_path):
        """Test get_stats returns expected data"""
        custom_path = tmp_path / "custom_store"
        store = VectorStore(store_path=str(custom_path))
        stats = store.get_stats()
        assert "store_path" in stats
        assert "embedding_dim" in stats
        assert "collection_name" in stats
        assert stats["embedding_dim"] == 768
