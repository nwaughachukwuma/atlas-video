"""
Integration tests for Atlas — testing component interactions.
"""
# ruff: noqa: D102

from unittest.mock import AsyncMock, MagicMock, patch  # , PropertyMock

import pytest

from atlas.utils import VideoAttrAnalysis
from atlas.vector_store import VideoIndex  # , SearchResult
from atlas.video_processor import (
    VideoDescription,
    VideoProcessor,
    VideoProcessorConfig,
    VideoProcessorResult,
)


class TestVideoIndexIntegration:
    """Integration tests for VideoIndex with zvec"""

    @pytest.fixture
    def temp_col_path(self, tmp_path):
        return tmp_path / "video_index"

    @pytest.fixture
    def sample_video_result(self):
        analysis1 = VideoAttrAnalysis(attr="visual_cues", value="A person walking in a park")
        analysis2 = VideoAttrAnalysis(attr="audio_analysis", value="Birds chirping")
        desc = VideoDescription(
            start=0.0,
            end=10.0,
            video_analysis=[analysis1, analysis2],
        )
        return VideoProcessorResult(
            video_path="/tmp/test_video.mp4",
            duration=10.0,
            transcript="",
            video_descriptions=[desc],
        )

    def test_initialization(self, temp_col_path):
        vi = VideoIndex(col_path=temp_col_path)
        assert vi.embedding_dim == 768
        # col_path is not created until first collection access
        assert not temp_col_path.exists()

    @pytest.mark.zvec
    def test_registry_starts_empty(self, temp_col_path):
        vi = VideoIndex(col_path=temp_col_path)
        assert vi.list_videos() == []

    @pytest.mark.zvec
    @pytest.mark.asyncio
    async def test_index_and_search_flow(self, temp_col_path, sample_video_result: VideoProcessorResult, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        vi = VideoIndex(col_path=temp_col_path)
        video_id = "test_video_id_001"
        mock_embedding = [0.1] * 768

        # Only the Gemini embedding call is mocked — zvec runs for real.

        # # Mock the embedding call and the zvec-dependent layer so the test runs
        # # on platforms where zvec is not installed (e.g. macOS x86_64).
        # mock_collection = MagicMock()
        with (
            patch("atlas.text_embedding.embed_text", new_callable=AsyncMock, return_value=mock_embedding),
            # patch.object(type(vi), "collection", new_callable=PropertyMock, return_value=mock_collection),
            # patch.object(vi, "_make_doc", return_value=MagicMock()),
        ):
            indexed = await vi.index_video_result(sample_video_result, video_id=video_id)
            assert indexed > 0

            # # Patch search to verify the returned interface
            # with patch.object(vi, "search", new_callable=AsyncMock) as mock_search:
            #     mock_search.return_value = [
            #         SearchResult(
            #             id="test_id",
            #             score=0.9,
            #             video_id=video_id,
            #             start=0.0,
            #             end=10.0,
            #             content="test content",
            #             metadata={"attr": "visual_cues", "duration": 10.0},
            #         )
            #     ]
            #     results = await vi.search("person walking", top_k=5, video_id=video_id)
            #     assert len(results) > 0
            #     assert results[0].score == 0.9
            #     assert results[0].video_id == video_id

            # list_videos() exercises the zvec query path.
            videos = vi.list_videos()
            assert any(v.video_id == video_id for v in videos)
            # search() exercises the zvec vector-query path.
            results = await vi.search("person walking", top_k=5, video_id=video_id)
            assert len(results) > 0
            assert all(r.video_id == video_id for r in results)


class TestVideoProcessorIntegration:
    """Integration tests for VideoProcessor"""

    @pytest.fixture
    def sample_video_path(self, tmp_path):
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()
        return str(video_path)

    @pytest.mark.asyncio
    async def test_processor_config_flow(self, sample_video_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        config = VideoProcessorConfig(
            video_path=sample_video_path,
            chunk_duration=5,
            overlap=1,
            description_attrs=["visual_cues"],
        )

        with patch("atlas.gemini_client.GeminiClient.get_client"):
            processor = VideoProcessor(config)
            processor._duration = 10.0

            assert processor.chunk_duration == 5
            assert processor.overlap == 1

    @pytest.mark.asyncio
    async def test_chunk_slicing_with_overlap(self, sample_video_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        config = VideoProcessorConfig(
            video_path=sample_video_path,
            chunk_duration=5,
            overlap=1,
        )

        with patch("atlas.gemini_client.GeminiClient.get_client"):
            processor = VideoProcessor(config)
            processor._duration = 15.0

            slots = processor._slice_media_file(5, 1)
            # With 15s duration, 5s chunks, 1s overlap:
            # 0-5, 4-9, 8-13, 12-15 (approx)
            assert len(slots) >= 3


class TestCLIIntegration:
    """Integration tests for CLI commands"""

    def test_cli_import(self):
        from atlas.cli import main

        assert callable(main)

    def test_cli_parse_duration(self):
        from atlas.cli import parse_duration

        assert parse_duration("15s") == 15
        assert parse_duration("1m") == 60
        assert parse_duration("1m30s") == 90
        assert parse_duration("1h") == 3600
        assert parse_duration("30") == 30
        assert parse_duration("1h30m15s") == 5415

    def test_cli_validate_video_path(self, tmp_path):
        from atlas.cli import validate_video_path

        # Valid path
        video_path = tmp_path / "test.mp4"
        video_path.touch()
        result = validate_video_path(str(video_path))
        assert result == video_path

        # Invalid path should raise SystemExit
        with pytest.raises(SystemExit):
            validate_video_path("/nonexistent/video.mp4")


class TestEndToEnd:
    """End-to-end tests for complete workflows"""

    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    @pytest.fixture
    def sample_video(self, tmp_path):
        video_path = tmp_path / "sample.mp4"
        video_path.touch()
        return str(video_path)

    @pytest.mark.asyncio
    async def test_get_video_transcript_workflow(self, sample_video, mock_env_vars):
        with patch("atlas.transcript.ProcessTranscript") as mock_transcript:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value="Test transcript content")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=True)
            mock_transcript.return_value = mock_instance

            from atlas.video_processor import get_video_transcript

            result = await get_video_transcript(sample_video)
            assert isinstance(result, str)

    def test_package_imports(self, mock_env_vars):
        import atlas

        assert atlas.__version__ is not None
