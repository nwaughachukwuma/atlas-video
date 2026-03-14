"""
Pytest configuration and shared fixtures for Atlas tests
"""

import json
import sys
import warnings
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.atlas.utils import VideoAttrAnalysis
from src.atlas.video_processor import VideoDescription, VideoProcessorResult, compile_transcript

from .helpers import async_gen

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _has_zvec() -> bool:
    try:
        import zvec  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


ZVEC_AVAILABLE = _has_zvec()


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
        transcript=compile_transcript([sample_video_description]),
        video_descriptions=[sample_video_description],
    )


@pytest.fixture
def mock_embedding():
    """Create a mock embedding vector"""
    return [0.1] * 768


@pytest.fixture
def mock_gemini_client():
    """Mock the Gemini client"""
    with (
        patch("atlas.gemini_client.get_gemini_client") as mock_get_client,
        patch("atlas.gemini_client.get_gemini_aio_client") as mock_get_aio_client,
    ):
        mock = MagicMock()
        mock.aio = MagicMock()
        mock_get_client.return_value = mock
        mock_get_aio_client.return_value = mock.aio
        yield mock


@pytest.fixture
def mock_gemini_client_with_chunks(mock_gemini_client):
    """Fixture to create a mock Gemini client that yields specified chunks."""

    def _factory(chunks):
        mock_stream = async_gen(*chunks)
        mock_aclient = MagicMock()
        mock_aclient.models.generate_content_stream = AsyncMock(return_value=mock_stream)
        mock_gemini_client.aio = mock_aclient
        return mock_gemini_client

    return _factory


@pytest.fixture
def mock_groq_client():
    """Mock the Groq client"""
    with patch("atlas.transcript.Groq") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked with @pytest.mark.zvec when zvec is not importable."""
    if not ZVEC_AVAILABLE:
        skip = pytest.mark.skip(reason="zvec native extension not available on this host")
        for item in items:
            if item.get_closest_marker("zvec"):
                item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def mock_zvec_init_when_unavailable():
    """Patch BaseCollection init for local hosts where zvec cannot be installed."""
    if ZVEC_AVAILABLE:
        yield
        return

    warnings.warn(
        "zvec is not installed on this host; zvec-marked tests will be skipped and BaseCollection._init_zvec "
        "is mocked for host-only unit tests.",
        RuntimeWarning,
        stacklevel=1,
    )

    with ExitStack() as stack:
        for module_name in ("atlas.vector_store.base", "src.atlas.vector_store.base"):
            try:
                module = import_module(module_name)
            except ModuleNotFoundError:
                continue
            stack.enter_context(patch.object(module.BaseCollection, "_init_zvec", return_value=None))
        yield


# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop_policy():
    """Configure event loop policy for async tests"""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="package")
def mock_model_dump_json():
    """Fixture to create a MagicMock with model_dump_json side effect."""

    def _factory(obj: dict):
        mock = MagicMock()
        # Attach model_dump_json as a method that returns the JSON string
        mock.model_dump_json = MagicMock(side_effect=lambda **kwargs: json.dumps(obj, **kwargs))
        return mock

    return _factory


@pytest.fixture(scope="package")
def mock_model_dump():
    """Generic fixture to mock Pydantic's model_dump for any MagicMock."""

    def _factory(**model_dump_return_value):
        mock = MagicMock()
        mock.model_dump = MagicMock(return_value=model_dump_return_value)
        return mock

    return _factory


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-api-key")
