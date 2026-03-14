# ruff: noqa: D102

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.chat_handler import _stream_response, chat_with_video
from atlas.vector_store import SearchResult
from atlas.vector_store.video_chat import ChatResult, ChatRole

from .helpers import async_gen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_search_result(content: str, video_id: str = "vid_001") -> SearchResult:
    return SearchResult(
        id="sr-1",
        score=0.9,
        video_id=video_id,
        start=0.0,
        end=5.0,
        content=content,
    )


def _make_chat_result(content: str, role: ChatRole = "user", video_id: str = "vid_001") -> ChatResult:
    return ChatResult(
        id="cr-1",
        score=0.8,
        video_id=video_id,
        role=role,
        content=content,
    )


# ---------------------------------------------------------------------------
# Chat workflow tests
# ---------------------------------------------------------------------------


class TestChatWorkflow:
    """Tests for the chat_with_video pipeline in atlas.chat_handler."""

    @pytest.fixture
    def mock_vi(self):
        vi = MagicMock()
        vi.search = AsyncMock(return_value=[_make_search_result("A person walks in a park")])
        return vi

    @pytest.fixture
    def mock_vc(self):
        vc = MagicMock()
        vc.get_history = MagicMock(
            return_value=[{"role": "user", "content": "Hello", "timestamp": "2026-01-01T00:00:00"}]
        )
        vc.search = AsyncMock(return_value=[_make_chat_result("Hello")])
        vc.record_turn = AsyncMock()
        return vc

    @pytest.fixture
    def patch_stores(self, mock_vi, mock_vc):
        with (
            patch("atlas.chat_handler.default_video_index", return_value=mock_vi),
            patch("atlas.chat_handler.default_video_chat", return_value=mock_vc),
        ):
            yield mock_vi, mock_vc

    @pytest.mark.asyncio
    async def test_streams_chunks(self, patch_stores):
        """chat_with_video yields text chunks from _stream_response."""
        with patch("atlas.chat_handler._stream_response", return_value=async_gen("Hello", " world")):
            chunks = [chunk async for chunk in chat_with_video("vid_001", "What is in the video?")]

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_persists_both_turns(self, patch_stores):
        """After streaming, record_turn is called for user then assistant."""
        _, mock_vc = patch_stores

        with patch("atlas.chat_handler._stream_response", return_value=async_gen("Great video!")):
            _ = [chunk async for chunk in chat_with_video("vid_001", "Describe the video")]

        assert mock_vc.record_turn.await_count == 2
        calls = mock_vc.record_turn.await_args_list
        assert calls[0].args == ("vid_001", "user", "Describe the video")
        assert calls[1].args == ("vid_001", "assistant", "Great video!")

    @pytest.mark.asyncio
    async def test_raises_on_empty_response(self, patch_stores):
        """chat_with_video raises ValueError when Gemini returns an empty string."""
        with patch("atlas.chat_handler._stream_response", return_value=async_gen("   ")):
            with pytest.raises(ValueError, match="Empty response"):
                _ = [chunk async for chunk in chat_with_video("vid_001", "anything")]

    @pytest.mark.asyncio
    async def test_deduplicates_semantic_hits(self, patch_stores):
        """Semantic chat hits already present in ordered history are excluded from extra_context."""
        mock_vi, mock_vc = patch_stores

        # History contains "Hello"; semantic search also returns "Hello" + a new message
        mock_vc.get_history.return_value = [{"role": "user", "content": "Hello", "timestamp": "t0"}]
        mock_vc.search.return_value = [
            _make_chat_result("Hello"),  # duplicate — should be excluded
            _make_chat_result("Birds are chirping"),  # new — should be included
        ]

        captured_extra: list[list[str]] = []

        async def capturing_stream_response(**kwargs):
            captured_extra.append(kwargs["extra_context"])
            yield "ok"

        with patch("atlas.chat_handler._stream_response", side_effect=capturing_stream_response):
            _ = [chunk async for chunk in chat_with_video("vid_001", "Tell me more")]

        assert captured_extra[0] == ["Birds are chirping"]
        assert "Hello" not in captured_extra[0]

    @pytest.mark.asyncio
    async def test_passes_top_k_to_stores(self, patch_stores):
        """top_k_context and top_k_chat are forwarded to the underlying store searches."""
        mock_vi, mock_vc = patch_stores

        with patch("atlas.chat_handler._stream_response", return_value=async_gen("answer")):
            _ = [chunk async for chunk in chat_with_video("vid_001", "query", top_k_context=3, top_k_chat=5)]

        mock_vi.search.assert_awaited_once_with("query", top_k=3, video_id="vid_001")
        mock_vc.search.assert_awaited_once_with("query", video_id="vid_001", top_k=5)


class TestStreamResponse:
    """Tests for _stream_response — the Gemini streaming helper."""

    def _make_chunk(self, text: str | None):
        chunk = MagicMock()
        chunk.text = text
        return chunk

    @pytest.mark.asyncio
    async def test_yields_text_chunks(self, mock_gemini_client_with_chunks):
        """_stream_response yields .text from each Gemini chunk."""
        chunks = [self._make_chunk("Hello"), self._make_chunk(" world")]
        mock_gemini_client = mock_gemini_client_with_chunks(chunks)
        with patch("atlas.gemini_client.get_gemini_aio_client", return_value=mock_gemini_client.aio):
            result = [
                chunk
                async for chunk in _stream_response(
                    query="What is this?",
                    video_context=["park scene"],
                    history=[],
                    extra_context=[],
                )
            ]

        assert result == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_skips_chunks_without_text(self, mock_gemini_client_with_chunks):
        """Chunks with falsy .text (None or empty string) are not yielded."""
        chunks = [
            self._make_chunk("Real text"),
            self._make_chunk(None),
            self._make_chunk(""),
            self._make_chunk("More text"),
        ]
        mock_gemini_client = mock_gemini_client_with_chunks(chunks)
        with (
            patch("atlas.gemini_client.get_gemini_aio_client", return_value=mock_gemini_client.aio),
        ):
            result = [
                chunk
                async for chunk in _stream_response(
                    query="What is this?",
                    video_context=[],
                    history=[],
                    extra_context=[],
                )
            ]

        assert result == ["Real text", "More text"]
