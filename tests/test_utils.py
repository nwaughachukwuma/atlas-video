"""
Unit tests for atlas.utils module
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.atlas.utils import (
    ChunkSlot,
    MediaChunk,
    MediaFileManager,
    RetryConfig,
    TempPath,
    VideoAttrAnalysis,
    delete_tmp_files,
    logger,
    process_time,
    retry,
    to_sexagesimal,
)


class TestTempPath:
    """Tests for TempPath class"""

    def test_get_temp_dir_creates_directory(self):
        """Test that get_temp_dir creates a directory"""
        TempPath._temp_dir = None  # Reset
        temp_dir = TempPath.get_temp_dir()
        assert temp_dir is not None
        assert os.path.exists(temp_dir)
        assert "atlas_" in temp_dir

    def test_get_path_creates_file(self):
        """Test that get_path creates a temporary file path"""
        path = TempPath.get_path(ext=".mp4")
        assert path.endswith(".mp4")
        assert os.path.exists(path) or Path(path).parent.exists()

    def test_cleanup_removes_directory(self):
        """Test that cleanup removes the temp directory"""
        TempPath._temp_dir = None
        _ = TempPath.get_temp_dir()
        TempPath.cleanup()
        assert TempPath._temp_dir is None


class TestDeleteTmpFiles:
    """Tests for delete_tmp_files function"""

    def test_deletes_existing_files(self):
        """Test that existing files are deleted"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        assert os.path.exists(temp_path)
        delete_tmp_files([temp_path])
        assert not os.path.exists(temp_path)

    def test_handles_none_values(self):
        """Test that None values are handled gracefully"""
        delete_tmp_files([None, None])  # Should not raise

    def test_handles_nonexistent_files(self):
        """Test that nonexistent files are handled gracefully"""
        delete_tmp_files(["/nonexistent/file.mp4"])  # Should not raise


class TestToSexagesimal:
    """Tests for to_sexagesimal function"""

    def test_converts_seconds(self):
        """Test conversion of seconds to sexagesimal"""
        assert to_sexagesimal(0) == "00:00:00.000"
        assert to_sexagesimal(1.5) == "00:00:01.500"
        assert to_sexagesimal(60) == "00:01:00.000"
        assert to_sexagesimal(3661.123) == "01:01:01.123"

    def test_handles_float_values(self):
        """Test that float values are handled correctly"""
        result = to_sexagesimal(90.567)
        assert "00:01:30.567" == result


class TestChunkSlot:
    """Tests for ChunkSlot model"""

    def test_creates_slot(self):
        """Test ChunkSlot creation"""
        slot = ChunkSlot(start=0.0, end=10.0)
        assert slot.start == 0.0
        assert slot.end == 10.0


class TestMediaChunk:
    """Tests for MediaChunk model"""

    def test_creates_chunk(self):
        """Test MediaChunk creation"""
        chunk = MediaChunk(path="/tmp/video.mp4", start=0.0, end=10.0)
        assert chunk.path == "/tmp/video.mp4"
        assert chunk.start == 0.0
        assert chunk.end == 10.0


class TestVideoAttrAnalysis:
    """Tests for VideoAttrAnalysis model"""

    def test_creates_analysis(self):
        """Test VideoAttrAnalysis creation"""
        analysis = VideoAttrAnalysis(attr="visual_cues", value="Test description")
        assert analysis.attr == "visual_cues"
        assert analysis.value == "Test description"


class TestRetryConfig:
    """Tests for RetryConfig model"""

    def test_default_values(self):
        """Test default RetryConfig values"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.delay == 1.0
        assert config.backoff == 2.0

    def test_custom_values(self):
        """Test custom RetryConfig values"""
        config = RetryConfig(max_retries=5, delay=2.0, backoff=3.0)
        assert config.max_retries == 5
        assert config.delay == 2.0
        assert config.backoff == 3.0


class TestRetryDecorator:
    """Tests for retry decorator"""

    def test_retries_on_exception(self):
        """Test that retry retries on exception"""
        call_count = 0

        @retry(RetryConfig(max_retries=3, delay=0.1))
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"

        result = failing_func()
        assert result == "success"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        """Test that retry raises after max retries"""

        @retry(RetryConfig(max_retries=2, delay=0.1))
        def always_failing():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_failing()

    @pytest.mark.asyncio
    async def test_async_retry(self):
        """Test that retry works with async functions"""
        call_count = 0

        @retry(RetryConfig(max_retries=3, delay=0.1))
        async def async_failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"

        result = await async_failing_func()
        assert result == "success"
        assert call_count == 3


class TestProcessTime:
    """Tests for process_time decorator"""

    def test_logs_time(self):
        """Test that process_time logs execution time"""

        @process_time()
        def test_func():
            return "result"

        with patch.object(logger, "info") as mock_info:
            result = test_func()
            assert result == "result"
            mock_info.assert_called_once()
            assert "completed in" in mock_info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_async_process_time(self):
        """Test that process_time works with async functions"""

        @process_time()
        async def async_test_func():
            return "async_result"

        with patch.object(logger, "info") as mock_info:
            result = await async_test_func()
            assert result == "async_result"
            mock_info.assert_called_once()


class TestMediaFileManager:
    """Tests for MediaFileManager class"""

    def test_file_ext_property(self, tmp_path):
        """Test file_ext property returns correct extension"""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        manager = MediaFileManager(str(video_path))
        assert manager.file_ext == ".mp4"

    def test_slice_media_file(self, tmp_path):
        """Test _slice_media_file creates correct slots"""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        manager = MediaFileManager(str(video_path))
        manager._duration = 30.0

        slots = manager._slice_media_file(10)
        assert len(slots) == 3
        assert slots[0].start == 0.0
        assert slots[0].end == 10.0
        assert slots[2].start == 20.0
        assert slots[2].end == 30.0

    def test_slice_media_file_with_overlap(self, tmp_path):
        """Test _slice_media_file with overlap creates correct slots"""
        video_path = tmp_path / "test_video.mp4"
        video_path.touch()

        manager = MediaFileManager(str(video_path))
        manager._duration = 30.0

        slots = manager._slice_media_file(10, overlap=2)
        assert len(slots) == 4  # More slots due to overlap
        assert slots[0].start == 0.0
        assert slots[0].end == 10.0
        assert slots[1].start == 8.0  # 10 - 2 overlap
        assert slots[1].end == 18.0
