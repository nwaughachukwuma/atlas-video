"""
Unit tests for atlas.video_processor module
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.utils import VideoAttrAnalysis
from atlas.video_processor import (
    VideoDescription,
    VideoProcessor,
    VideoProcessorConfig,
    VideoProcessorResult,
)


class TestVideoProcessorConfig:
    """Tests for VideoProcessorConfig model"""

    def test_default_values(self):
        """Test default config values"""
        config = VideoProcessorConfig(video_path="/tmp/video.mp4")
        assert config.video_path == "/tmp/video.mp4"
        assert config.chunk_duration == 15
        assert config.overlap == 1
        assert config.description_attrs is None
        assert config.include_summary is True

    def test_custom_values(self):
        """Test custom config values"""
        config = VideoProcessorConfig(
            video_path="/tmp/video.mp4",
            chunk_duration=15,
            overlap=2,
            description_attrs=["visual_cues"],
            include_summary=True,
        )
        assert config.chunk_duration == 15
        assert config.overlap == 2
        assert config.description_attrs == ["visual_cues"]
        assert config.include_summary is True


class TestVideoDescription:
    """Tests for VideoDescription model"""

    def test_creates_description(self):
        """Test VideoDescription creation"""
        analysis = VideoAttrAnalysis(attr="visual_cues", value="Test")
        desc = VideoDescription(
            start=0.0,
            end=10.0,
            video_analysis=[analysis],
        )
        assert desc.start == 0.0
        assert desc.end == 10.0
        assert desc.summary is None
        assert len(desc.video_analysis) == 1

    def test_with_summary(self):
        """Test VideoDescription with summary"""
        desc = VideoDescription(
            start=0.0,
            end=10.0,
            summary="Test summary",
            video_analysis=[],
        )
        assert desc.summary == "Test summary"


class TestVideoProcessorResult:
    """Tests for VideoProcessorResult model"""

    def test_creates_result(self):
        """Test VideoProcessorResult creation"""
        result = VideoProcessorResult(
            video_path="/tmp/video.mp4",
            duration=30.0,
            transcript="Test transcript",
            video_descriptions=[],
        )
        assert result.video_path == "/tmp/video.mp4"
        assert result.duration == 30.0
        assert result.transcript == "Test transcript"
        assert len(result.video_descriptions) == 0


class TestVideoProcessor:
    """Tests for VideoProcessor class"""

    def test_initialization(self, tmp_path, mock_gemini_client):
        """Test VideoProcessor initialization"""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        config = VideoProcessorConfig(video_path=str(video_path))
        processor = VideoProcessor(config)

        assert processor.video_path == str(video_path)
        assert processor.chunk_duration == 15
        assert processor.overlap == 1

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_path, mock_gemini_client):
        """Test VideoProcessor as context manager"""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        config = VideoProcessorConfig(video_path=str(video_path))
        async with VideoProcessor(config) as processor:
            assert processor is not None
            assert processor.video_path == str(video_path)

    @pytest.mark.asyncio
    async def test_context_manager_does_not_suppress_exceptions(self, tmp_path, mock_gemini_client):
        """Test VideoProcessor context manager propagates exceptions."""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        config = VideoProcessorConfig(video_path=str(video_path))

        with pytest.raises(RuntimeError, match="boom"):
            async with VideoProcessor(config):
                raise RuntimeError("boom")

    @pytest.mark.asyncio
    async def test_analyze_chunk_content_falls_back_on_transcript_error(
        self, tmp_path, monkeypatch, mock_gemini_client
    ):
        """Test transcript failures produce an empty transcript attribute."""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        config = VideoProcessorConfig(video_path=str(video_path))
        processor = VideoProcessor(config)
        processor.describe_media_from_file = AsyncMock(return_value=MagicMock(_to_attr_list=lambda: []))

        async def _raise_transcript_error(_chunk_path):
            raise RuntimeError("transcript failed")

        monkeypatch.setattr("atlas.video_processor.get_video_transcript", _raise_transcript_error)

        result = await processor.analyze_chunk_content(MagicMock(), str(video_path))

        assert result == [VideoAttrAnalysis(value="", attr="transcript")]
