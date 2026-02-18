"""
Unit tests for atlas.cli — argument parser, helpers, and command handlers.

Strategy
--------
* Parser tests call _build_parser().parse_args() with synthetic argv — no side
  effects, no I/O.
* Helper tests call the pure utility functions directly.
* Command handler tests call _cmd_* directly with an argparse.Namespace, mocking
  every I/O boundary (file-system, network, vector store, asyncio.run).
"""
# ruff: noqa: D102

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from atlas.cli import (
    _build_parser,
    _cmd_chat,
    _cmd_extract,
    _cmd_index,
    _cmd_list_chat,
    _cmd_list_videos,
    _cmd_search,
    _cmd_stats,
    _cmd_transcribe,
    _format_elapsed,
    _short_name,
    parse_duration,
    validate_api_keys,
    validate_video_path,
)

from .helpers import mock_asyncio_run

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser() -> argparse.ArgumentParser:
    return _build_parser()


@pytest.fixture()
def progress_ctx():
    """A mock that behaves as both a context manager and a rich Progress object."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.add_task.return_value = 0
    return ctx


# ---------------------------------------------------------------------------
# TestParserConstruction — every subcommand + key flags
# ---------------------------------------------------------------------------


class TestParserConstruction:
    """Verify the argument parser structure without executing any I/O."""

    def test_all_subcommands_registered(self, parser):
        subparsers_action = next(a for a in parser._actions if hasattr(a, "_name_parser_map"))
        registered = set(subparsers_action._name_parser_map.keys())
        assert registered == {
            "extract",
            "index",
            "search",
            "transcribe",
            "chat",
            "list-videos",
            "list-chat",
            "stats",
        }

    # ---- extract ----

    def test_extract_defaults(self, parser):
        ns = parser.parse_args(["extract", "video.mp4"])
        assert ns.video_path == "video.mp4"
        assert ns.chunk_duration == "15s"
        assert ns.overlap == "1s"
        assert ns.attrs is None
        assert ns.output is None
        assert ns.format == "text"
        assert ns.include_summary is True
        assert ns.benchmark is False

    def test_extract_no_summary_flag(self, parser):
        ns = parser.parse_args(["extract", "video.mp4", "--no-summary"])
        assert ns.include_summary is False

    def test_extract_json_format(self, parser):
        ns = parser.parse_args(["extract", "video.mp4", "--format", "json"])
        assert ns.format == "json"

    def test_extract_multiple_attrs(self, parser):
        ns = parser.parse_args(["extract", "video.mp4", "-a", "visual_cues", "-a", "transcript"])
        assert ns.attrs == ["visual_cues", "transcript"]

    def test_extract_output_flag(self, parser):
        ns = parser.parse_args(["extract", "video.mp4", "-o", "out.json"])
        assert ns.output == "out.json"

    def test_extract_chunk_and_overlap(self, parser):
        ns = parser.parse_args(["extract", "video.mp4", "-c", "30s", "-l", "2s"])
        assert ns.chunk_duration == "30s"
        assert ns.overlap == "2s"

    # ---- index ----

    def test_index_defaults(self, parser):
        ns = parser.parse_args(["index", "video.mp4"])
        assert ns.video_path == "video.mp4"
        assert ns.chunk_duration == "15s"
        assert ns.overlap == "0s"
        assert ns.store_path is None
        assert ns.embedding_dim == 768

    def test_index_custom_flags(self, parser):
        ns = parser.parse_args(["index", "video.mp4", "-c", "20s", "-o", "2s", "-s", "/tmp/idx", "-e", "3072"])
        assert ns.chunk_duration == "20s"
        assert ns.overlap == "2s"
        assert ns.store_path == "/tmp/idx"
        assert ns.embedding_dim == 3072

    # ---- search ----

    def test_search_defaults(self, parser):
        ns = parser.parse_args(["search", "hello world"])
        assert ns.query == "hello world"
        assert ns.top_k == 10
        assert ns.video_id is None
        assert ns.store_path is None

    def test_search_custom_flags(self, parser):
        ns = parser.parse_args(["search", "q", "-k", "5", "-v", "vid1", "-s", "/idx"])
        assert ns.top_k == 5
        assert ns.video_id == "vid1"
        assert ns.store_path == "/idx"

    # ---- transcribe ----

    def test_transcribe_defaults(self, parser):
        ns = parser.parse_args(["transcribe", "video.mp4"])
        assert ns.video_path == "video.mp4"
        assert ns.format == "text"
        assert ns.output is None

    def test_transcribe_srt(self, parser):
        ns = parser.parse_args(["transcribe", "video.mp4", "-f", "srt", "-o", "out.srt"])
        assert ns.format == "srt"
        assert ns.output == "out.srt"

    # ---- chat ----

    def test_chat_args(self, parser):
        ns = parser.parse_args(["chat", "vid1", "What is this about?"])
        assert ns.video_id == "vid1"
        assert ns.query == "What is this about?"
        assert ns.store_path is None

    # ---- list-videos ----

    def test_list_videos_defaults(self, parser):
        ns = parser.parse_args(["list-videos"])
        assert ns.store_path is None

    def test_list_videos_store_path(self, parser):
        ns = parser.parse_args(["list-videos", "-s", "/tmp/idx"])
        assert ns.store_path == "/tmp/idx"

    # ---- list-chat ----

    def test_list_chat_defaults(self, parser):
        ns = parser.parse_args(["list-chat", "vid1"])
        assert ns.video_id == "vid1"
        assert ns.last_n == 20
        assert ns.store_path is None

    def test_list_chat_last_n(self, parser):
        ns = parser.parse_args(["list-chat", "vid1", "-n", "5"])
        assert ns.last_n == 5

    # ---- stats ----

    def test_stats_defaults(self, parser):
        ns = parser.parse_args(["stats"])
        assert ns.store_path is None

    # ---- shared --benchmark flag ----

    def test_benchmark_flag_propagates(self, parser):
        for cmd in [
            ["extract", "v.mp4", "--benchmark"],
            ["index", "v.mp4", "--benchmark"],
            ["search", "q", "--benchmark"],
            ["list-videos", "--benchmark"],
            ["stats", "--benchmark"],
        ]:
            ns = parser.parse_args(cmd)
            assert ns.benchmark is True, f"--benchmark not set for: {cmd}"

    def test_no_subcommand_exits(self, parser):
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_func_set_correctly(self, parser):
        mapping = {
            "extract": (_cmd_extract, ["extract", "v.mp4"]),
            "index": (_cmd_index, ["index", "v.mp4"]),
            "search": (_cmd_search, ["search", "q"]),
            "transcribe": (_cmd_transcribe, ["transcribe", "v.mp4"]),
            "chat": (_cmd_chat, ["chat", "vid1", "q?"]),
            "list-videos": (_cmd_list_videos, ["list-videos"]),
            "list-chat": (_cmd_list_chat, ["list-chat", "vid1"]),
            "stats": (_cmd_stats, ["stats"]),
        }
        for cmd_name, (expected_fn, argv) in mapping.items():
            ns = parser.parse_args(argv)
            assert ns.func is expected_fn, f"Wrong func for {cmd_name}"


# ---------------------------------------------------------------------------
# TestHelpers — pure utility functions
# ---------------------------------------------------------------------------


class TestShortName:
    def test_strips_module_prefix(self):
        assert _short_name("atlas.utils.MediaFileManager._clip") == "_clip"

    def test_single_component(self):
        assert _short_name("_clip") == "_clip"

    def test_two_components(self):
        assert _short_name("module.func") == "func"


class TestFormatElapsed:
    def test_sub_minute(self):
        assert _format_elapsed(0.91) == "0.91s"
        assert _format_elapsed(59.99) == "59.99s"

    def test_minutes(self):
        assert _format_elapsed(90.0) == "1m 30s"
        assert _format_elapsed(60.0) == "1m 0s"

    def test_hours(self):
        assert _format_elapsed(3661.0) == "1h 1m 1s"
        assert _format_elapsed(3600.0) == "1h 0m 0s"


class TestParseDuration:
    def test_plain_int(self):
        assert parse_duration("30") == 30

    def test_seconds_suffix(self):
        assert parse_duration("15s") == 15

    def test_minutes_suffix(self):
        assert parse_duration("1m") == 60

    def test_minutes_and_seconds(self):
        assert parse_duration("1m30s") == 90

    def test_hours(self):
        assert parse_duration("1h") == 3600

    def test_full_hms(self):
        assert parse_duration("1h30m15s") == 5415

    def test_zero_string(self):
        assert parse_duration("0") == 0

    def test_invalid_format_exits(self):
        with pytest.raises(SystemExit):
            parse_duration("xyz")


class TestValidateVideoPath:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "video.mp4"
        f.touch()
        result = validate_video_path(str(f))
        assert result == f

    def test_nonexistent_exits(self):
        with pytest.raises(SystemExit):
            validate_video_path("/nonexistent/path/video.mp4")

    def test_directory_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            validate_video_path(str(tmp_path))


class TestValidateApiKeys:
    def test_passes_when_keys_present(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key1")
        monkeypatch.setenv("GROQ_API_KEY", "key2")
        # Should not raise
        validate_api_keys(require_gemini=True, require_groq=True)

    def test_exits_when_gemini_missing(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            validate_api_keys(require_gemini=True, require_groq=False)

    def test_exits_when_groq_missing(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key1")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            validate_api_keys(require_gemini=False, require_groq=True)

    def test_no_requirements_always_passes(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        validate_api_keys(require_gemini=False, require_groq=False)


# ---------------------------------------------------------------------------
# TestCmdIndex
# ---------------------------------------------------------------------------


class TestCmdIndex:
    def _args(self, video_path="/tmp/v.mp4", store_path=None):
        return argparse.Namespace(
            video_path=video_path,
            chunk_duration="15s",
            overlap="0s",
            store_path=store_path,
            embedding_dim=768,
            benchmark=False,
        )

    def test_success_prints_video_id(self, tmp_path, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        monkeypatch.setenv("GROQ_API_KEY", "k2")

        video = tmp_path / "v.mp4"
        video.touch()
        args = self._args(video_path=str(video))

        mock_result = MagicMock(duration=30.0, video_descriptions=[MagicMock()] * 3)

        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli._make_progress", return_value=progress_ctx),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value=("vid_001", 3, mock_result))),
        ):
            _cmd_index(args)  # must not raise

    def test_missing_api_key_exits(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        video = tmp_path / "v.mp4"
        video.touch()
        with pytest.raises(SystemExit):
            _cmd_index(self._args(str(video)))

    def test_bad_video_path_exits(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        monkeypatch.setenv("GROQ_API_KEY", "k2")
        with pytest.raises(SystemExit):
            _cmd_index(self._args("/no/such/file.mp4"))

    def test_exception_in_run_exits(self, tmp_path, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        monkeypatch.setenv("GROQ_API_KEY", "k2")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli._make_progress", return_value=progress_ctx),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("boom"))),
        ):
            with pytest.raises(SystemExit):
                _cmd_index(self._args(str(video)))


# ---------------------------------------------------------------------------
# TestCmdSearch
# ---------------------------------------------------------------------------


class TestCmdSearch:
    def _args(self, query="people talking", top_k=5, video_id=None, store_path=None):
        return argparse.Namespace(
            query=query,
            top_k=top_k,
            video_id=video_id,
            store_path=store_path,
            benchmark=False,
        )

    def test_success_with_results(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")

        mock_result = MagicMock(score=0.95, video_id="vid1", start=0.0, end=10.0, content="visual cues about people")

        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value=[mock_result])),
        ):
            _cmd_search(self._args())  # must not raise

    def test_empty_results_prints_message(self, monkeypatch, capsys):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")

        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value=[])),
        ):
            _cmd_search(self._args())  # no SystemExit — just a "no results" message

    def test_exception_exits(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("fail"))),
        ):
            with pytest.raises(SystemExit):
                _cmd_search(self._args())

    def test_missing_api_key_exits(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            _cmd_search(self._args())


# ---------------------------------------------------------------------------
# TestCmdChat
# ---------------------------------------------------------------------------


class TestCmdChat:
    def _args(self, video_id="vid1", query="What is this?", store_path=None):
        return argparse.Namespace(
            video_id=video_id,
            query=query,
            store_path=store_path,
            benchmark=False,
        )

    def test_success(self, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli._make_progress", return_value=progress_ctx),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value="Here is my answer.")),
        ):
            _cmd_chat(self._args())

    def test_missing_api_key_exits(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            _cmd_chat(self._args())

    def test_exception_exits(self, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli._make_progress", return_value=progress_ctx),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("network error"))),
        ):
            with pytest.raises(SystemExit):
                _cmd_chat(self._args())


# ---------------------------------------------------------------------------
# TestCmdListVideos
# ---------------------------------------------------------------------------


class TestCmdListVideos:
    def _args(self, store_path=None):
        return argparse.Namespace(store_path=store_path, benchmark=False)

    def test_no_videos(self):
        mock_vi = MagicMock()
        mock_vi.list_videos.return_value = []
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi):
            _cmd_list_videos(self._args())

    def test_with_videos(self):
        entry = MagicMock(video_id="vid_abc", indexed_at="2026-02-18T10:00:00")
        mock_vi = MagicMock()
        mock_vi.list_videos.return_value = [entry]
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi):
            _cmd_list_videos(self._args())

    def test_custom_store_path_forwarded(self):
        mock_vi = MagicMock()
        mock_vi.list_videos.return_value = []
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi) as mock_factory:
            _cmd_list_videos(self._args(store_path="/custom/path"))
            mock_factory.assert_called_once_with(store_path="/custom/path")


# ---------------------------------------------------------------------------
# TestCmdListChat
# ---------------------------------------------------------------------------


class TestCmdListChat:
    def _args(self, video_id="vid1", last_n=20, store_path=None):
        return argparse.Namespace(video_id=video_id, last_n=last_n, store_path=store_path, benchmark=False)

    def test_no_history(self):
        mock_vc = MagicMock()
        mock_vc.get_history.return_value = []
        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc):
            _cmd_list_chat(self._args())

    def test_with_history(self):
        mock_vc = MagicMock()
        mock_vc.get_history.return_value = [
            {"role": "user", "content": "hi", "timestamp": "2026-01-01T00:00:00"},
            {"role": "assistant", "content": "hello", "timestamp": "2026-01-01T00:00:01"},
        ]
        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc):
            _cmd_list_chat(self._args())

    def test_last_n_forwarded(self):
        mock_vc = MagicMock()
        mock_vc.get_history.return_value = []
        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc):
            _cmd_list_chat(self._args(last_n=5))
            mock_vc.get_history.assert_called_once_with("vid1", last_n=5)


# ---------------------------------------------------------------------------
# TestCmdStats
# ---------------------------------------------------------------------------


class TestCmdStats:
    def _args(self, store_path=None):
        return argparse.Namespace(store_path=store_path, benchmark=False)

    def test_success(self):
        mock_vi = MagicMock()
        mock_vi.index_path = Path("/tmp/vi")
        mock_vi.stats = {"count": 10}
        mock_vi.list_videos.return_value = []

        mock_vc = MagicMock()
        mock_vc.index_path = Path("/tmp/vc")
        mock_vc.stats = {"count": 5}

        with (
            patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi),
            patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc),
        ):
            _cmd_stats(self._args())

    def test_stats_exception_handled_gracefully(self):
        """If .stats raises (e.g. zvec not available), the command still completes."""
        mock_vi = MagicMock()
        mock_vi.index_path = Path("/tmp/vi")
        type(mock_vi).stats = property(lambda self: (_ for _ in ()).throw(RuntimeError("zvec unavail")))
        mock_vi.list_videos.return_value = []

        mock_vc = MagicMock()
        mock_vc.index_path = Path("/tmp/vc")
        type(mock_vc).stats = property(lambda self: (_ for _ in ()).throw(RuntimeError("zvec unavail")))

        with (
            patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi),
            patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc),
        ):
            _cmd_stats(self._args())  # must not raise


# ---------------------------------------------------------------------------
# TestCmdTranscribe
# ---------------------------------------------------------------------------


class TestCmdTranscribe:
    def _args(self, video_path="/tmp/v.mp4", fmt="text", output=None):
        return argparse.Namespace(video_path=video_path, format=fmt, output=output, benchmark=False)

    def test_success_text_to_stdout(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value="Hello world transcript")),
        ):
            _cmd_transcribe(self._args(str(video)))

    def test_success_saves_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        out = tmp_path / "out.srt"
        with (
            patch("atlas.cli.validate_api_keys"),
            patch(
                "atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value="1\n00:00:00 --> 00:00:10\nHello")
            ),
        ):
            _cmd_transcribe(self._args(str(video), fmt="srt", output=str(out)))

    def test_invalid_format_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with pytest.raises(SystemExit):
            _cmd_transcribe(self._args(str(video), fmt="xml"))

    def test_missing_groq_key_exits(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            _cmd_transcribe(self._args())

    def test_bad_video_path_exits(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        with pytest.raises(SystemExit):
            _cmd_transcribe(self._args("/no/file.mp4"))

    def test_exception_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("fail"))),
        ):
            with pytest.raises(SystemExit):
                _cmd_transcribe(self._args(str(video)))


# ---------------------------------------------------------------------------
# TestCmdExtract
# ---------------------------------------------------------------------------


class TestCmdExtract:
    def _args(self, video_path="/tmp/v.mp4", fmt="text", output=None, attrs=None, include_summary=True):
        return argparse.Namespace(
            video_path=video_path,
            chunk_duration="15s",
            overlap="1s",
            attrs=attrs,
            output=output,
            format=fmt,
            include_summary=include_summary,
            benchmark=False,
        )

    def test_success_text_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        mock_result = MagicMock(duration=10.0, video_descriptions=[])
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value=mock_result)),
        ):
            _cmd_extract(self._args(str(video)))

    def test_success_json_to_stdout(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        mock_result = MagicMock(duration=10.0, video_descriptions=[])
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value=mock_result)),
        ):
            _cmd_extract(self._args(str(video), fmt="json"))
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert data["duration"] == 10.0

    def test_success_json_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        out = tmp_path / "out.json"
        mock_result = MagicMock(duration=10.0, video_descriptions=[])
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(return_value=mock_result)),
        ):
            _cmd_extract(self._args(str(video), fmt="json", output=str(out)))
        assert out.exists()

    def test_invalid_attr_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with patch("atlas.cli.validate_api_keys"):
            with pytest.raises(SystemExit):
                _cmd_extract(self._args(str(video), attrs=["invalid_attr"]))

    def test_invalid_format_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with patch("atlas.cli.validate_api_keys"):
            with pytest.raises(SystemExit):
                _cmd_extract(self._args(str(video), fmt="yaml"))

    def test_missing_api_key_exits(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        video = tmp_path / "v.mp4"
        video.touch()
        with pytest.raises(SystemExit):
            _cmd_extract(self._args(str(video)))

    def test_bad_video_path_exits(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with pytest.raises(SystemExit):
            _cmd_extract(self._args("/no/file.mp4"))

    def test_exception_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.validate_api_keys"),
            patch("atlas.cli.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("gpu error"))),
        ):
            with pytest.raises(SystemExit):
                _cmd_extract(self._args(str(video)))
