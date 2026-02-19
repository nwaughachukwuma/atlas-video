"""
Unit tests for atlas.vector_store — VideoIndex and VideoChat collections.
"""
# ruff: noqa: D102

from src.atlas.utils import VideoAttrAnalysis
from src.atlas.vector_store import (
    ChatDocument,
    ChatResult,
    IndexDocument,
    SearchResult,
    VideoChat,
    VideoEntry,
    VideoIndex,
)
from src.atlas.vector_store.video_chat import default_video_chat
from src.atlas.vector_store.video_index import DEFAULT_STORE_ROOT, default_video_index
from src.atlas.video_processor import VideoDescription

# ---------------------------------------------------------------------------
# IndexDocument
# ---------------------------------------------------------------------------


class TestIndexDocument:
    """Tests for IndexDocument model"""

    def test_creates_document(self):
        doc = IndexDocument(
            id="doc123",
            video_id="vid_abc",
            start=0.0,
            end=10.0,
            content="Test content",
            embedding=[0.1] * 768,
        )
        assert doc.id == "doc123"
        assert doc.video_id == "vid_abc"
        assert doc.start == 0.0
        assert doc.end == 10.0
        assert doc.content == "Test content"
        assert len(doc.embedding) == 768

    def test_with_metadata(self):
        doc = IndexDocument(
            id="doc123",
            video_id="vid_abc",
            start=0.0,
            end=10.0,
            content="Test content",
            embedding=[0.1] * 768,
            metadata={"attr": "visual_cues"},
        )
        assert doc.metadata == {"attr": "visual_cues"}


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------


class TestSearchResult:
    """Tests for SearchResult model"""

    def test_creates_result(self):
        result = SearchResult(
            id="doc123",
            score=0.95,
            video_id="vid_abc",
            start=0.0,
            end=10.0,
            content="Test content",
        )
        assert result.id == "doc123"
        assert result.score == 0.95
        assert result.video_id == "vid_abc"
        assert result.start == 0.0
        assert result.end == 10.0
        assert result.content == "Test content"

    def test_with_metadata(self):
        result = SearchResult(
            id="doc123",
            score=0.95,
            video_id="vid_abc",
            start=0.0,
            end=10.0,
            content="Test content",
            metadata={"attr": "visual_cues"},
        )
        assert result.metadata == {"attr": "visual_cues"}


# ---------------------------------------------------------------------------
# ChatDocument / ChatResult
# ---------------------------------------------------------------------------


class TestChatDocument:
    """Tests for ChatDocument model"""

    def test_creates_user_message(self):
        doc = ChatDocument(
            id="chat001",
            video_id="vid_abc",
            role="user",
            content="What is happening in this video?",
            embedding=[0.2] * 768,
        )
        assert doc.role == "user"
        assert doc.video_id == "vid_abc"

    def test_creates_assistant_message(self):
        doc = ChatDocument(
            id="chat002",
            video_id="vid_abc",
            role="assistant",
            content="The video shows a person walking in a park.",
            embedding=[0.3] * 768,
        )
        assert doc.role == "assistant"


class TestChatResult:
    """Tests for ChatResult model"""

    def test_creates_result(self):
        result = ChatResult(
            id="chat001",
            score=0.88,
            video_id="vid_abc",
            role="user",
            content="What is happening?",
        )
        assert result.score == 0.88
        assert result.role == "user"
        assert result.video_id == "vid_abc"


# ---------------------------------------------------------------------------
# VideoEntry
# ---------------------------------------------------------------------------


class TestVideoEntry:
    """Tests for VideoEntry model"""

    def test_creates_entry(self):
        entry = VideoEntry(video_id="vid_abc", indexed_at="2026-01-01T00:00:00")
        assert entry.video_id == "vid_abc"
        assert entry.indexed_at == "2026-01-01T00:00:00"


# ---------------------------------------------------------------------------
# VideoIndex
# ---------------------------------------------------------------------------


class TestVideoIndex:
    """Tests for VideoIndex collection class"""

    def test_initialization(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        assert vi.embedding_dim == 768
        assert vi.col_path == tmp_path / "video_index"

    def test_custom_embedding_dim(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "vi", embedding_dim=3072)
        assert vi.embedding_dim == 3072

    def test_registry_path(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        assert vi._registry_path == tmp_path / "video_index" / "registry.json"

    def test_uuid(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        doc_id = vi._uuid()
        assert isinstance(doc_id, str)
        assert len(doc_id) == 16

    def test_create_searchable_content(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        analysis1 = VideoAttrAnalysis(attr="visual_cues", value="A person walking")
        analysis2 = VideoAttrAnalysis(attr="audio_analysis", value="Background music")
        desc = VideoDescription(
            start=0.0,
            end=10.0,
            video_analysis=[analysis1, analysis2],
        )
        content = vi._create_searchable_content(desc)
        assert "VISUAL CUES: A person walking" in content
        assert "AUDIO ANALYSIS: Background music" in content

    def test_list_videos_empty(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        assert vi.list_videos() == []

    def test_register_and_list(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        vi.col_path.mkdir(parents=True, exist_ok=True)
        vi.register("vid_001")
        vi.register("vid_002")
        # Duplicate should be ignored
        vi.register("vid_001")

        videos = vi.list_videos()
        ids = [v.video_id for v in videos]
        assert "vid_001" in ids
        assert "vid_002" in ids
        assert ids.count("vid_001") == 1

    def test_unregister(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        vi.col_path.mkdir(parents=True, exist_ok=True)
        vi.register("vid_001")
        vi.register("vid_002")
        vi.unregister("vid_001")

        ids = [v.video_id for v in vi.list_videos()]
        assert "vid_001" not in ids
        assert "vid_002" in ids

    def testdefault_video_index_helper(self):
        vi = default_video_index()
        assert vi.col_path == DEFAULT_STORE_ROOT / "video_index"
        assert vi.embedding_dim == 768


# ---------------------------------------------------------------------------
# VideoChat
# ---------------------------------------------------------------------------


class TestVideoChat:
    """Tests for VideoChat collection class"""

    def test_initialization(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        assert vc.embedding_dim == 768
        assert vc.col_path == tmp_path / "video_chat"

    def test_sidecar_path(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        vc.col_path.mkdir(parents=True, exist_ok=True)
        path = vc._sidecar_path("vid_xyz")
        assert path == tmp_path / "video_chat" / "logs" / "vid_xyz.jsonl"

    def test_append_and_get_history(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        vc.append_to_history("vid_xyz", "user", "Hello, what is this video?")
        vc.append_to_history("vid_xyz", "assistant", "This video shows a park scene.")

        history = vc.get_history("vid_xyz")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert "park" in history[1]["content"]

    def test_get_history_empty(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        history = vc.get_history("nonexistent_video")
        assert history == []

    def test_get_history_last_n(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        for i in range(10):
            vc.append_to_history("vid_xyz", "user", f"Question {i}")
            vc.append_to_history("vid_xyz", "assistant", f"Answer {i}")

        history = vc.get_history("vid_xyz", last_n=6)
        assert len(history) == 6

    def testdefault_video_chat_helper(self):
        vc = default_video_chat()
        assert vc.col_path == DEFAULT_STORE_ROOT / "video_chat"
        assert vc.embedding_dim == 768

    def test_uuid(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        doc_id = vc._uuid()
        assert isinstance(doc_id, str)
        assert len(doc_id) == 16
