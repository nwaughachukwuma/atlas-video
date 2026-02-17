"""
Pytest configuration and shared fixtures for Atlas tests
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.atlas.utils import VideoAttrAnalysis
import pytest
from src.atlas.video_processor import VideoDescription
from src.atlas.video_processor import VideoProcessorResult

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_gemini_api_key(monkeypatch):
    """Set mock Gemini API key"""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")


@pytest.fixture
def mock_groq_api_key(monkeypatch):
    """Set mock Groq API key"""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-api-key")


@pytest.fixture
def mock_api_keys(mock_gemini_api_key, mock_groq_api_key):
    """Set all required API keys"""
    pass


@pytest.fixture
def temp_video_file(tmp_path):
    """Create a temporary video file for testing"""
    video_path = tmp_path / "test_video.mp4"
    video_path.touch()
    return str(video_path)


@pytest.fixture
def temp_audio_file(tmp_path):
    """Create a temporary audio file for testing"""
    audio_path = tmp_path / "test_audio.mp3"
    audio_path.touch()
    return str(audio_path)


@pytest.fixture
def temp_store_path(tmp_path):
    """Create a temporary vector store path"""
    return tmp_path / "test_vector_store"


@pytest.fixture
def sample_video_attr_analysis():
    """Create sample VideoAttrAnalysis objects"""

    return [
        VideoAttrAnalysis(attr="visual_cues", value="A person walking in a park"),
        VideoAttrAnalysis(attr="audio_analysis", value="Birds chirping in background"),
        VideoAttrAnalysis(attr="transcript", value="Hello, this is a test transcript"),
        VideoAttrAnalysis(attr="interactions", value="Person waves at camera"),
        VideoAttrAnalysis(attr="contextual_information", value="Outdoor sunny day"),
    ]


@pytest.fixture
def sample_video_description(sample_video_attr_analysis):
    """Create a sample VideoDescription"""

    return VideoDescription(
        start=0.0,
        end=10.0,
        summary="A person walks in a park on a sunny day",
        video_analysis=sample_video_attr_analysis,
    )


@pytest.fixture
def sample_video_processor_result(sample_video_description):
    """Create a sample VideoProcessorResult"""

    return VideoProcessorResult(
        video_path="/tmp/test_video.mp4",
        duration=10.0,
        transcript="Test transcript content",
        video_descriptions=[sample_video_description],
    )


@pytest.fixture
def mock_embedding():
    """Create a mock embedding vector"""
    return [0.1] * 768


@pytest.fixture
def mock_gemini_client():
    """Mock the Gemini client"""
    with patch("atlas.gemini_client.GeminiClient") as mock:
        mock_instance = MagicMock()
        mock.get_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_groq_client():
    """Mock the Groq client"""
    with patch("atlas.transcript.Groq") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop_policy():
    """Configure event loop policy for async tests"""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
