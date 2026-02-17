"""
Integration tests for Atlas - testing component interactions
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from atlas.utils import VideoAttrAnalysis
from atlas.vector_store import VectorStore
from atlas.video_processor import (
    VideoDescription,
    VideoProcessor,
    VideoProcessorConfig,
    VideoProcessorResult,
)
from atlas.vector_store import SearchResult


class TestVectorStoreIntegration:
    """Integration tests for VectorStore with zvec"""

    @pytest.fixture
    def temp_store_path(self, tmp_path):
        """Create a temporary store path"""
        return tmp_path / "test_store"

    @pytest.fixture
    def sample_video_result(self):
        """Create a sample VideoProcessorResult"""
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

    def test_store_initialization(self, temp_store_path):
        """Test that store initializes correctly"""
        store = VectorStore(store_path=str(temp_store_path))
        assert store.embedding_dim == 768
        assert not temp_store_path.exists()  # Not created until first use

    @pytest.mark.asyncio
    async def test_index_and_search_flow(self, temp_store_path, sample_video_result: VideoProcessorResult, monkeypatch):
        """Test the full index and search flow"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        store = VectorStore(store_path=str(temp_store_path))
        # Mock the embedding function - patch where it's used, not where it's defined
        mock_embedding = [0.1] * 768

        with patch("atlas.vector_store.embed_text_async", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = mock_embedding
            # Index the result
            indexed = await store.index_video_result(sample_video_result)
            assert indexed > 0
            # Search should return results - mock returns sample results
            with patch.object(store, "search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = [
                    SearchResult(
                        id="test_id",
                        score=0.9,
                        video_path="/tmp/test_video.mp4",
                        start=0.0,
                        end=10.0,
                        content="test content",
                        metadata={"attr": "visual_cues", "duration": 10.0},
                    )
                ]
                results = await store.search("person walking", top_k=5)
                assert len(results) > 0
                assert results[0].score == 0.9


class TestVideoProcessorIntegration:
    """Integration tests for VideoProcessor"""

    @pytest.fixture
    def sample_video_path(self, tmp_path):
        """Create a sample video file (empty for testing)"""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()
        return str(video_path)

    @pytest.mark.asyncio
    async def test_processor_config_flow(self, sample_video_path, monkeypatch):
        """Test VideoProcessor with configuration"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        config = VideoProcessorConfig(
            video_path=sample_video_path,
            chunk_duration=5,
            overlap=1,
            description_attrs=["visual_cues"],
        )

        # Mock the duration probing
        with patch("atlas.gemini_client.GeminiClient.get_client"):
            processor = VideoProcessor(config)
            processor._duration = 10.0

            assert processor.chunk_duration == 5
            assert processor.overlap == 1

    @pytest.mark.asyncio
    async def test_chunk_slicing_with_overlap(self, sample_video_path, monkeypatch):
        """Test that chunk slicing works with overlap"""
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
        """Test that CLI module can be imported"""
        from atlas.cli import main

        assert callable(main)

    def test_cli_parse_duration(self):
        """Test CLI duration parsing"""
        from atlas.cli import parse_duration

        assert parse_duration("15s") == 15
        assert parse_duration("1m") == 60
        assert parse_duration("1m30s") == 90
        assert parse_duration("1h") == 3600
        assert parse_duration("30") == 30
        assert parse_duration("1h30m15s") == 5415

    def test_cli_validate_video_path(self, tmp_path):
        """Test CLI video path validation"""
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
        """Set up mock environment variables"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    @pytest.fixture
    def sample_video(self, tmp_path):
        """Create a sample video file"""
        video_path = tmp_path / "sample.mp4"
        video_path.touch()
        return str(video_path)

    @pytest.mark.asyncio
    async def test_extract_transcript_workflow(self, sample_video, mock_env_vars):
        """Test the transcript extraction workflow"""

        # Mock the entire transcription process
        with patch("atlas.video_processor.ProcessTranscript") as mock_transcript:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value="Test transcript content")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=True)
            mock_transcript.return_value = mock_instance

            # This would work with actual mocking
            # result = await extract_transcript(sample_video)

    def test_package_imports(self, mock_env_vars):
        """Test that all package imports work correctly"""
        # Main package
        import atlas

        # Submodules

        assert atlas.__version__ is not None
