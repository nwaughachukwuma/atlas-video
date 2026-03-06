"""
Unit tests for atlas.vector_store — VideoIndex and VideoChat collections.
"""
# ruff: noqa: D102

from unittest.mock import MagicMock, patch

import pytest

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
from src.atlas.vector_store.base import BaseCollection, get_or_create_collection
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
        mock_col = MagicMock()
        mock_col.query.return_value = []
        vi._collection = mock_col
        with patch("src.atlas.vector_store.video_index.make_vector_query", return_value=MagicMock()):
            assert vi.list_videos() == []

    def test_list_videos_deduplicates(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        mock_col = MagicMock()
        r1 = MagicMock()
        r1.field.side_effect = lambda f: {
            "video_id": "vid_001",
            "metadata": '{"indexed_at": "2026-01-01T00:00:00"}',
        }[f]
        r2 = MagicMock()
        r2.field.side_effect = lambda f: {
            "video_id": "vid_001",
            "metadata": '{"indexed_at": "2026-01-01T00:01:00"}',
        }[f]
        r3 = MagicMock()
        r3.field.side_effect = lambda f: {
            "video_id": "vid_002",
            "metadata": '{"indexed_at": "2026-01-02T00:00:00"}',
        }[f]
        mock_col.query.return_value = [r1, r2, r3]
        vi._collection = mock_col

        with patch("src.atlas.vector_store.video_index.make_vector_query", return_value=MagicMock()):
            videos = vi.list_videos()
        ids = [v.video_id for v in videos]
        assert "vid_001" in ids
        assert "vid_002" in ids
        assert ids.count("vid_001") == 1
        # Should keep earliest timestamp
        vid_001 = next(v for v in videos if v.video_id == "vid_001")
        assert vid_001.indexed_at == "2026-01-01T00:00:00"

    def test_get_video_data(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        mock_col = MagicMock()
        # Main document (no attr)
        r_main = MagicMock()
        r_main.field.side_effect = lambda f: {
            "start": 0.0,
            "end": 10.0,
            "video_id": "vid_001",
            "content": "VISUAL CUES: walking\nAUDIO ANALYSIS: music",
            "metadata": '{"duration": 10.0, "indexed_at": "2026-01-01", "summary": "A person walks with music."}',
        }[f]
        # Per-attribute document
        r_attr = MagicMock()
        r_attr.field.side_effect = lambda f: {
            "start": 0.0,
            "end": 10.0,
            "video_id": "vid_001",
            "content": "visual_cues: A person walking in a park",
            "metadata": '{"duration": 10.0, "indexed_at": "2026-01-01", "attr": "visual_cues"}',
        }[f]
        mock_col.query.return_value = [r_main, r_attr]
        vi._collection = mock_col

        with patch("src.atlas.vector_store.video_index.make_vector_query", return_value=MagicMock()):
            data = vi.get_video_data("vid_001")
        assert data is not None
        assert data["video_id"] == "vid_001"
        assert data["segments_count"] == 1
        seg = data["video_descriptions"][0]
        assert seg["summary"] == "A person walks with music."
        assert len(seg["video_analysis"]) == 1
        assert seg["video_analysis"][0]["attr"] == "visual_cues"

    def test_get_video_data_not_found(self, tmp_path):
        vi = VideoIndex(col_path=tmp_path / "video_index")
        mock_col = MagicMock()
        mock_col.query.return_value = []
        vi._collection = mock_col
        with patch("src.atlas.vector_store.video_index.make_vector_query", return_value=MagicMock()):
            assert vi.get_video_data("nonexistent") is None

    def testdefault_video_index_helper(self):
        vi = default_video_index()
        assert vi.col_path == DEFAULT_STORE_ROOT / "video_index"
        assert vi.embedding_dim == 768

    def test_collection_reuses_shared_handle(self, tmp_path):
        shared = MagicMock()
        with (
            patch.object(BaseCollection, "_init_zvec", return_value=None),
            patch.object(VideoIndex, "_build_schema", return_value=MagicMock()),
            patch.dict("src.atlas.vector_store.base._collection_cache", {}, clear=True),
            patch("src.atlas.vector_store.base.get_or_create_collection", return_value=shared) as open_collection,
        ):
            first = VideoIndex(col_path=tmp_path / "video_index")
            second = VideoIndex(col_path=tmp_path / "video_index")

            assert first.collection is shared
            assert second.collection is shared

        open_collection.assert_called_once()


class TestBaseCollectionHelpers:
    def test_get_or_create_collection_creates_for_empty_existing_directory(self, tmp_path):
        collection_path = tmp_path / "video_index"
        collection_path.mkdir()
        fake_zvec = MagicMock()
        created = MagicMock()
        fake_zvec.create_and_open.return_value = created

        with patch.dict("sys.modules", {"zvec": fake_zvec}):
            result = get_or_create_collection(str(collection_path), MagicMock())

        assert result is created
        fake_zvec.open.assert_not_called()
        fake_zvec.create_and_open.assert_called_once()

    def test_get_or_create_collection_raises_without_deleting_existing_path(self, tmp_path):
        collection_path = tmp_path / "video_index"
        collection_path.mkdir()
        (collection_path / "existing").write_text("initialized")
        fake_zvec = MagicMock()
        fake_zvec.open.side_effect = RuntimeError("Can't lock read-write collection")

        with patch.dict("sys.modules", {"zvec": fake_zvec}):
            with pytest.raises(RuntimeError, match="Unable to open zvec collection"):
                get_or_create_collection(str(collection_path), MagicMock())

        assert collection_path.exists()
        fake_zvec.create_and_open.assert_not_called()


# ---------------------------------------------------------------------------
# VideoChat
# ---------------------------------------------------------------------------


class TestVideoChat:
    """Tests for VideoChat collection class"""

    def test_initialization(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        assert vc.embedding_dim == 768
        assert vc.col_path == tmp_path / "video_chat"

    def test_get_history_from_zvec(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        mock_col = MagicMock()
        r1 = MagicMock()
        r1.field.side_effect = lambda f: {
            "role": "user",
            "content": "Hello, what is this video?",
            "metadata": '{"timestamp": "2026-01-01T00:00:00"}',
        }[f]
        r2 = MagicMock()
        r2.field.side_effect = lambda f: {
            "role": "assistant",
            "content": "This video shows a park scene.",
            "metadata": '{"timestamp": "2026-01-01T00:00:01"}',
        }[f]
        # Return out of order to test sorting
        mock_col.query.return_value = [r2, r1]
        vc._collection = mock_col

        with patch("src.atlas.vector_store.video_chat.make_vector_query", return_value=MagicMock()):
            history = vc.get_history("vid_xyz")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert "park" in history[1]["content"]

    def test_get_history_empty(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        mock_col = MagicMock()
        mock_col.query.return_value = []
        vc._collection = mock_col
        with patch("src.atlas.vector_store.video_chat.make_vector_query", return_value=MagicMock()):
            history = vc.get_history("nonexistent_video")
        assert history == []

    def test_get_history_last_n(self, tmp_path):
        vc = VideoChat(col_path=tmp_path / "video_chat")
        mock_col = MagicMock()
        results = []
        for i in range(20):
            r = MagicMock()
            role = "user" if i % 2 == 0 else "assistant"
            r.field.side_effect = lambda f, _i=i, _role=role: {
                "role": _role,
                "content": f"Message {_i}",
                "metadata": f'{{"timestamp": "2026-01-01T00:00:{_i:02d}"}}',
            }[f]
            results.append(r)
        mock_col.query.return_value = results
        vc._collection = mock_col

        with patch("src.atlas.vector_store.video_chat.make_vector_query", return_value=MagicMock()):
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
