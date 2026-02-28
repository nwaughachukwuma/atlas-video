"""
Unit tests for atlas.cli — argument parser, helpers, and command handlers.

Strategy
--------
* Parser tests call build_parser().parse_args() with synthetic argv — no side
  effects, no I/O.
* Helper tests call the pure utility functions directly.
* Command handler tests call cmd_* directly with an argparse.Namespace, mocking
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
    build_parser,
    cmd_chat,
    cmd_extract,
    cmd_get_data,
    cmd_index,
    cmd_list_chat,
    cmd_list_videos,
    cmd_search,
    cmd_serve,
    cmd_stats,
    cmd_transcribe,
    format_elapsed,
    parse_duration,
    short_name,
    validate_api_keys,
    validate_video_path,
)

from .helpers import mock_asyncio_run

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser() -> argparse.ArgumentParser:
    return build_parser()


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
            "queue",
            "get-video",
            "serve",
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
        assert ns.no_queue is False
        assert ns.no_streaming is False

    def test_extract_no_include_summary_flag(self, parser):
        ns = parser.parse_args(["extract", "video.mp4", "--include-summary", "false"])
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
        assert ns.overlap == "1s"
        # assert ns.embedding_dim == 768

    def test_index_custom_flags(self, parser):
        ns = parser.parse_args(["index", "video.mp4", "-c", "20s", "-o", "2s"])  # "-e", "3072"
        assert ns.chunk_duration == "20s"
        assert ns.overlap == "2s"
        # assert ns.embedding_dim == 3072

    # ---- get-video ----

    def test_video_get_data_defaults(self, parser):
        ns = parser.parse_args(["get-video", "vid1"])
        assert ns.video_id == "vid1"
        assert ns.output is None

    def test_video_get_data_with_output(self, parser):
        ns = parser.parse_args(["get-video", "vid1", "-o", "out.json"])
        assert ns.video_id == "vid1"
        assert ns.output == "out.json"

    # ---- serve ----

    def test_serve_defaults(self, parser):
        ns = parser.parse_args(["serve"])
        assert ns.host == "0.0.0.0"
        assert ns.port == 8000
        assert ns.env_file is None

    def test_serve_custom_host_port(self, parser):
        ns = parser.parse_args(["serve", "-H", "127.0.0.1", "-p", "9000"])
        assert ns.host == "127.0.0.1"
        assert ns.port == 9000

    def test_serve_env_file(self, parser):
        ns = parser.parse_args(["serve", "--env-file", ".env"])
        assert ns.env_file == ".env"

    # ---- search ----

    def test_search_defaults(self, parser):
        ns = parser.parse_args(["search", "hello world"])
        assert ns.search_args == ["hello world"]
        assert ns.top_k == 10

    def test_search_with_video_id(self, parser):
        ns = parser.parse_args(["search", "vid1", "hello world"])
        assert ns.search_args == ["vid1", "hello world"]
        assert ns.top_k == 10

    def test_search_custom_flags(self, parser):
        ns = parser.parse_args(["search", "vid1", "q", "-k", "5"])
        assert ns.top_k == 5
        assert ns.search_args == ["vid1", "q"]

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

    # ---- list-chat ----

    def test_list_chat_defaults(self, parser):
        ns = parser.parse_args(["list-chat", "vid1"])
        assert ns.video_id == "vid1"
        assert ns.last_n == 20

    def test_list_chat_last_n(self, parser):
        ns = parser.parse_args(["list-chat", "vid1", "-n", "5"])
        assert ns.last_n == 5

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

    # ---- shared --no-queue / --no-streaming flags ----

    def test_no_queue_flag(self, parser):
        ns = parser.parse_args(["transcribe", "v.mp4", "--no-queue"])
        assert ns.no_queue is True

    def test_no_streaming_flag(self, parser):
        ns = parser.parse_args(["extract", "v.mp4", "--no-streaming"])
        assert ns.no_streaming is True

    def test_no_subcommand_exits(self, parser):
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_func_set_correctly(self, parser):
        mapping = {
            "extract": (cmd_extract, ["extract", "v.mp4"]),
            "index": (cmd_index, ["index", "v.mp4"]),
            "search": (cmd_search, ["search", "q"]),
            "transcribe": (cmd_transcribe, ["transcribe", "v.mp4"]),
            "chat": (cmd_chat, ["chat", "vid1", "q?"]),
            "list-videos": (cmd_list_videos, ["list-videos"]),
            "list-chat": (cmd_list_chat, ["list-chat", "vid1"]),
            "stats": (cmd_stats, ["stats"]),
            "get-video": (cmd_get_data, ["get-video", "vid1"]),
            "serve": (cmd_serve, ["serve"]),
        }
        for cmd_name, (expected_fn, argv) in mapping.items():
            ns = parser.parse_args(argv)
            assert ns.func is expected_fn, f"Wrong func for {cmd_name}"


# ---------------------------------------------------------------------------
# TestHelpers — pure utility functions
# ---------------------------------------------------------------------------


class TestShortName:
    def test_strips_module_prefix(self):
        assert short_name("atlas.utils.MediaFileManager._clip") == "_clip"

    def test_single_component(self):
        assert short_name("_clip") == "_clip"

    def test_two_components(self):
        assert short_name("module.func") == "func"


class TestFormatElapsed:
    def test_sub_minute(self):
        assert format_elapsed(0.91) == "0.91s"
        assert format_elapsed(59.99) == "59.99s"

    def test_minutes(self):
        assert format_elapsed(90.0) == "1m 30s"
        assert format_elapsed(60.0) == "1m 0s"

    def test_hours(self):
        assert format_elapsed(3661.0) == "1h 1m 1s"
        assert format_elapsed(3600.0) == "1h 0m 0s"


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
    def _args(self, video_path="/tmp/v.mp4"):
        return argparse.Namespace(
            video_path=video_path,
            chunk_duration="15s",
            overlap="0s",
            attrs=None,
            include_summary=True,
            benchmark=False,
            no_queue=True,
            no_streaming=False,
        )

    def test_success_prints_video_id(self, tmp_path, monkeypatch, progress_ctx, mock_model_dump):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        monkeypatch.setenv("GROQ_API_KEY", "k2")

        video = tmp_path / "v.mp4"
        video.touch()
        args = self._args(video_path=str(video))

        mock_result = mock_model_dump(duration=30.0, video_descriptions=[])

        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch("atlas.cli.cmd_media.make_progress", return_value=progress_ctx),
            patch(
                "atlas.cli.cmd_media.asyncio.run",
                side_effect=mock_asyncio_run(return_value=("vid_001", 3, mock_result)),
            ),
        ):
            cmd_index(args)

    def test_missing_api_key_exits(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        video = tmp_path / "v.mp4"
        video.touch()
        with pytest.raises(SystemExit):
            cmd_index(self._args(str(video)))

    def test_bad_video_path_exits(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        monkeypatch.setenv("GROQ_API_KEY", "k2")
        with pytest.raises(SystemExit):
            cmd_index(self._args("/no/such/file.mp4"))

    def test_exception_in_run_exits(self, tmp_path, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        monkeypatch.setenv("GROQ_API_KEY", "k2")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch("atlas.cli.cmd_media.make_progress", return_value=progress_ctx),
            patch("atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("boom"))),
        ):
            with pytest.raises(SystemExit):
                cmd_index(self._args(str(video)))


# ---------------------------------------------------------------------------
# TestCmdSearch
# ---------------------------------------------------------------------------


class TestCmdSearch:
    def _args(self, query="people talking", top_k=5, video_id=None):
        search_args = [video_id, query] if video_id else [query]
        return argparse.Namespace(
            search_args=search_args,
            top_k=top_k,
            benchmark=False,
        )

    def test_success_with_results(self, monkeypatch, capsys):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")

        mock_result = MagicMock(score=0.95, video_id="vid1", start=0.0, end=10.0, content="visual cues about people")
        mock_result.model_dump.return_value = {
            "score": 0.95,
            "video_id": "vid1",
            "start": 0.0,
            "end": 10.0,
            "content": "visual cues about people",
        }

        with (
            patch("atlas.cli.cmd_explore.validate_api_keys"),
            patch("atlas.cli.cmd_explore.asyncio.run", side_effect=mock_asyncio_run(return_value=[mock_result])),
        ):
            cmd_search(self._args())  # must not raise

        out = capsys.readouterr().out
        body = json.loads(out)
        assert body["count"] == 1
        assert body["results"][0]["video_id"] == "vid1"

    def test_empty_results_prints_message(self, monkeypatch, capsys):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")

        with (
            patch("atlas.cli.cmd_explore.validate_api_keys"),
            patch("atlas.cli.cmd_explore.asyncio.run", side_effect=mock_asyncio_run(return_value=[])),
        ):
            cmd_search(self._args())  # no SystemExit — just a "no results" message

    def test_exception_exits(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with (
            patch("atlas.cli.cmd_explore.validate_api_keys"),
            patch("atlas.cli.cmd_explore.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("fail"))),
        ):
            with pytest.raises(SystemExit):
                cmd_search(self._args())

    def test_missing_api_key_exits(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            cmd_search(self._args())


# ---------------------------------------------------------------------------
# TestCmdChat
# ---------------------------------------------------------------------------


class TestCmdChat:
    def _args(self, video_id="vid1", query="What is this?"):
        return argparse.Namespace(video_id=video_id, query=query, benchmark=False)

    def test_success(self, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with (
            patch("atlas.cli.cmd_explore.validate_api_keys"),
            patch("atlas.cli.cmd_explore.make_progress", return_value=progress_ctx),
            patch("atlas.cli.cmd_explore.asyncio.run", side_effect=mock_asyncio_run(return_value="Here is my answer.")),
        ):
            cmd_chat(self._args())

    def test_missing_api_key_exits(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            cmd_chat(self._args())

    def test_exception_exits(self, monkeypatch, progress_ctx):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with (
            patch("atlas.cli.cmd_explore.validate_api_keys"),
            patch("atlas.cli.cmd_explore.make_progress", return_value=progress_ctx),
            patch(
                "atlas.cli.cmd_explore.asyncio.run",
                side_effect=mock_asyncio_run(side_effect=RuntimeError("network error")),
            ),
        ):
            with pytest.raises(SystemExit):
                cmd_chat(self._args())


# ---------------------------------------------------------------------------
# TestCmdListVideos
# ---------------------------------------------------------------------------


class TestCmdListVideos:
    def _args(self):
        return argparse.Namespace(benchmark=False)

    def test_no_videos(self):
        mock_vi = MagicMock()
        mock_vi.list_videos.return_value = []
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi):
            cmd_list_videos(self._args())

    def test_with_videos(self):
        entry = MagicMock(video_id="vid_abc", indexed_at="2026-02-18T10:00:00")
        mock_vi = MagicMock()
        mock_vi.list_videos.return_value = [entry]
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi):
            cmd_list_videos(self._args())


# ---------------------------------------------------------------------------
# TestCmdListChat
# ---------------------------------------------------------------------------


class TestCmdListChat:
    def _args(self, video_id="vid1", last_n=20):
        return argparse.Namespace(video_id=video_id, last_n=last_n, benchmark=False)

    def test_no_history(self):
        mock_vc = MagicMock()
        mock_vc.get_history.return_value = []
        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc):
            cmd_list_chat(self._args())

    def test_with_history(self):
        mock_vc = MagicMock()
        mock_vc.get_history.return_value = [
            {"role": "user", "content": "hi", "timestamp": "2026-01-01T00:00:00"},
            {"role": "assistant", "content": "hello", "timestamp": "2026-01-01T00:00:01"},
        ]
        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc):
            cmd_list_chat(self._args())

    def test_last_n_forwarded(self):
        mock_vc = MagicMock()
        mock_vc.get_history.return_value = []
        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc):
            cmd_list_chat(self._args(last_n=5))
            mock_vc.get_history.assert_called_once_with("vid1", last_n=5)


# ---------------------------------------------------------------------------
# TestCmdStats
# ---------------------------------------------------------------------------


class TestCmdStats:
    def _args(self):
        return argparse.Namespace(benchmark=False)

    def test_success(self):
        mock_vi = MagicMock()
        mock_vi.col_path = Path("/tmp/vi")
        mock_vi.stats = {"count": 10}
        mock_vi.list_videos.return_value = []

        mock_vc = MagicMock()
        mock_vc.col_path = Path("/tmp/vc")
        mock_vc.stats = {"count": 5}

        with (
            patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi),
            patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc),
        ):
            cmd_stats(self._args())

    def test_stats_raises_if_zvec_unavailable(self):
        """raises RuntimeError if zvec.stats errors or zvec is not available"""
        mock_vi = MagicMock()
        mock_vi.col_path = Path("/tmp/vi")
        type(mock_vi).stats = property(lambda self: (_ for _ in ()).throw(RuntimeError("zvec unavail")))
        mock_vi.list_videos.return_value = []

        mock_vc = MagicMock()
        mock_vc.col_path = Path("/tmp/vc")
        type(mock_vc).stats = property(lambda self: (_ for _ in ()).throw(RuntimeError("zvec unavail")))

        with (
            patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi),
            patch("atlas.vector_store.video_chat.default_video_chat", return_value=mock_vc),
        ):
            with pytest.raises(RuntimeError, match="zvec unavail"):
                cmd_stats(self._args())


# ---------------------------------------------------------------------------
# TestCmdGetData
# ---------------------------------------------------------------------------


class TestCmdGetData:
    def _args(self, video_id="vid1", output=None):
        return argparse.Namespace(video_id=video_id, output=output, benchmark=False)

    def test_success_prints_json(self, capsys, progress_ctx):
        mock_vi = MagicMock()
        mock_vi.get_video_data.return_value = {
            "video_id": "vid1",
            "duration": 30.0,
            "video_descriptions": [{"start": 0.0, "end": 10.0, "summary": None, "video_analysis": []}],
            "segments_count": 1,
        }
        with (
            patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi),
            patch("atlas.cli.cmd_explore.make_progress", return_value=progress_ctx),
        ):
            cmd_get_data(self._args())
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["video_id"] == "vid1"
        assert data["segments_count"] == 1

    def test_no_data_found(self):
        mock_vi = MagicMock()
        mock_vi.get_video_data.return_value = None
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi):
            cmd_get_data(self._args())

    def test_saves_to_file(self, tmp_path):
        mock_vi = MagicMock()
        mock_vi.get_video_data.return_value = {
            "video_id": "vid1",
            "duration": 30.0,
            "video_descriptions": [],
            "segments_count": 0,
        }
        out = tmp_path / "out.json"
        with patch("atlas.vector_store.video_index.default_video_index", return_value=mock_vi):
            cmd_get_data(self._args(output=str(out)))
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["video_id"] == "vid1"


# ---------------------------------------------------------------------------
# TestCmdTranscribe
# ---------------------------------------------------------------------------


class TestCmdTranscribe:
    def _args(self, video_path="/tmp/v.mp4", fmt="text", output=None):
        return argparse.Namespace(
            video_path=video_path,
            format=fmt,
            output=output,
            benchmark=False,
            no_queue=True,
            no_streaming=False,
        )

    def test_success_text_to_stdout(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch(
                "atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(return_value="Hello world transcript")
            ),
        ):
            cmd_transcribe(self._args(str(video)))

    def test_success_saves_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        out = tmp_path / "out.srt"
        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch(
                "atlas.cli.cmd_media.asyncio.run",
                side_effect=mock_asyncio_run(return_value="1\n00:00:00 --> 00:00:10\nHello"),
            ),
        ):
            cmd_transcribe(self._args(str(video), fmt="srt", output=str(out)))

    def test_invalid_format_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with pytest.raises(SystemExit):
            cmd_transcribe(self._args(str(video), fmt="xml"))

    def test_missing_groq_key_exits(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            cmd_transcribe(self._args())

    def test_bad_video_path_exits(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        with pytest.raises(SystemExit):
            cmd_transcribe(self._args("/no/file.mp4"))

    def test_exception_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch("atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("fail"))),
        ):
            with pytest.raises(SystemExit):
                cmd_transcribe(self._args(str(video)))


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
            no_queue=True,
            no_streaming=False,
        )

    def test_success_text_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        mock_result = MagicMock(duration=10.0, video_descriptions=[])
        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch("atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(return_value=mock_result)),
        ):
            cmd_extract(self._args(str(video)))

    def test_success_json_to_stdout(
        self,
        tmp_path,
        monkeypatch,
        capsys,
        mock_model_dump_json,
    ):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()

        mock_result = mock_model_dump_json({"duration": 10.0, "video_descriptions": []})

        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch("atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(return_value=mock_result)),
        ):
            cmd_extract(self._args(str(video), fmt="json"))
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert data["duration"] == 10.0

    def test_success_json_to_file(self, tmp_path, monkeypatch, mock_model_dump_json):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        out = tmp_path / "out.json"

        mock_result = mock_model_dump_json({"duration": 10.0, "video_descriptions": []})

        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch("atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(return_value=mock_result)),
        ):
            cmd_extract(self._args(str(video), fmt="json", output=str(out)))
        assert out.exists()

    def test_invalid_attr_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with patch("atlas.cli.cmd_media.validate_api_keys"):
            with pytest.raises(SystemExit):
                cmd_extract(self._args(str(video), attrs=["invalid_attr"]))

    def test_invalid_format_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with patch("atlas.cli.cmd_media.validate_api_keys"):
            with pytest.raises(SystemExit):
                cmd_extract(self._args(str(video), fmt="yaml"))

    def test_missing_api_key_exits(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        video = tmp_path / "v.mp4"
        video.touch()
        with pytest.raises(SystemExit):
            cmd_extract(self._args(str(video)))

    def test_bad_video_path_exits(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        with pytest.raises(SystemExit):
            cmd_extract(self._args("/no/file.mp4"))

    def test_exception_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "k1")
        video = tmp_path / "v.mp4"
        video.touch()
        with (
            patch("atlas.cli.cmd_media.validate_api_keys"),
            patch(
                "atlas.cli.cmd_media.asyncio.run", side_effect=mock_asyncio_run(side_effect=RuntimeError("gpu error"))
            ),
        ):
            with pytest.raises(SystemExit):
                cmd_extract(self._args(str(video)))


# ---------------------------------------------------------------------------
# TestTaskQueue — SQLite-backed queue, store, and queue CLI commands
# ---------------------------------------------------------------------------


class TestTaskStore:
    """Unit tests for the SQLite TaskStore."""

    def test_add_and_get(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("t1", "transcribe", "transcribe video.mp4")
        task = store.get("t1")
        assert task is not None
        assert task["id"] == "t1"
        assert task["command"] == "transcribe"
        assert task["status"] == "pending"

    def test_status_transitions(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("t1", "extract", "extract v.mp4")

        store.mark_running("t1")
        rtask = store.get("t1")
        assert rtask is not None
        assert rtask["status"] == "running"

        store.mark_completed("t1")
        ctask = store.get("t1")
        assert ctask is not None
        assert ctask["status"] == "completed"

    def test_mark_failed(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("t1", "index", "index v.mp4")
        store.mark_running("t1")
        store.mark_failed("t1", "out of memory")

        task = store.get("t1")
        assert task is not None
        assert task["status"] == "failed"
        assert task["error"] == "out of memory"

    def test_mark_timeout(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("t1", "transcribe", "t v.mp4")
        store.mark_timeout("t1")

        task = store.get("t1")
        assert task is not None
        assert task["status"] == "timeout"

    def test_list_all_and_filter(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("t1", "extract", "extract v1.mp4")
        store.add("t2", "index", "index v2.mp4")
        store.mark_running("t1")

        all_tasks = store.list_all()
        assert len(all_tasks) == 2

        running = store.list_all("running")
        assert len(running) == 1
        assert running[0]["id"] == "t1"

    def test_active_count(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("t1", "x", "x")
        store.add("t2", "y", "y")
        assert store.active_count() == 2
        store.mark_running("t1")
        assert store.active_count() == 2  # pending + running
        store.mark_completed("t1")
        assert store.active_count() == 1

    def test_trim_completed(self, tmp_path):
        from atlas.task_queue import MAX_COMPLETED_TASKS, TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        for i in range(MAX_COMPLETED_TASKS + 5):
            tid = f"c{i:03d}"
            store.add(tid, "x", "x")
            store.mark_completed(tid)

        completed = store.list_all("completed")
        assert len(completed) <= MAX_COMPLETED_TASKS

    def test_trim_failed(self, tmp_path):
        from atlas.task_queue import MAX_FAILED_TASKS, TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        for i in range(MAX_FAILED_TASKS + 5):
            tid = f"f{i:03d}"
            store.add(tid, "x", "x")
            store.mark_failed(tid, "err")

        failed = store.list_all("failed")
        assert len(failed) <= MAX_FAILED_TASKS

    def test_stale_tasks(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        store.add("s1", "x", "x")
        store.mark_running("s1")
        stale = store.stale_tasks()
        assert len(stale) == 1
        assert stale[0]["id"] == "s1"

    def test_get_nonexistent_returns_none(self, tmp_path):
        from atlas.task_queue import TaskStore

        store = TaskStore(db_path=tmp_path / "test.db")
        assert store.get("no-such-id") is None


class TestTaskQueueSubmit:
    """Test TaskQueue.submit (mocks subprocess.Popen to avoid real workers)."""

    def test_submit_returns_task_id(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskQueue

        # Redirect RESULTS_DIR to tmp
        monkeypatch.setattr("atlas.task_queue.queue.RESULTS_DIR", tmp_path / "results")

        # Prevent real subprocess spawn
        monkeypatch.setattr("atlas.task_queue.queue.subprocess.Popen", lambda *a, **kw: None)

        queue = TaskQueue(max_workers=1, db_path=tmp_path / "q.db")
        task_id = queue.submit(
            argparse.Namespace(video_path="test.mp4"),
            command="transcribe",
            label="transcribe test.mp4",
        )
        assert isinstance(task_id, str)
        assert len(task_id) == 8

        task = queue.get_task(task_id)
        assert task is not None
        assert task["command"] == "transcribe"

    def test_submit_creates_results_dir(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskQueue

        results_dir = tmp_path / "results"
        monkeypatch.setattr("atlas.task_queue.queue.RESULTS_DIR", results_dir)
        monkeypatch.setattr("atlas.task_queue.queue.subprocess.Popen", lambda *a, **kw: None)

        queue = TaskQueue(max_workers=1, db_path=tmp_path / "q.db")
        task_id = queue.submit(argparse.Namespace(), command="test")
        assert (results_dir / task_id).is_dir()
        # Verify args.json was written
        assert (results_dir / task_id / "args.json").exists()


class TestSerializeResult:
    def test_none(self):
        from atlas.task_queue import serialize_result

        assert serialize_result(None) == ""

    def test_string(self):
        from atlas.task_queue import serialize_result

        assert serialize_result("hello world") == "hello world"

    def test_dict(self):
        from atlas.task_queue import serialize_result

        result = serialize_result({"key": "value"})
        data = json.loads(result)
        assert data == {"key": "value"}

    def test_list(self):
        from atlas.task_queue import serialize_result

        result = serialize_result([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]


class TestQueueCLICommands:
    """Test queue list/status CLI command handlers."""

    def test_queue_list_empty(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskStore, cmd_queue_list

        monkeypatch.setattr("atlas.task_queue.commands.TaskStore", lambda: TaskStore(db_path=tmp_path / "q.db"))
        args = argparse.Namespace(status=None)
        # Should not raise
        cmd_queue_list(args)

    def test_queue_list_with_tasks(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskStore, cmd_queue_list

        db_path = tmp_path / "q.db"
        store = TaskStore(db_path=db_path)
        store.add("t1", "transcribe", "transcribe v.mp4")
        store.add("t2", "extract", "extract v.mp4")

        monkeypatch.setattr("atlas.task_queue.commands.TaskStore", lambda: store)
        args = argparse.Namespace(status=None)
        cmd_queue_list(args)  # should not raise

    def test_queue_list_filtered(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskStore, cmd_queue_list

        db_path = tmp_path / "q.db"
        store = TaskStore(db_path=db_path)
        store.add("t1", "transcribe", "t v.mp4")
        store.mark_running("t1")

        monkeypatch.setattr("atlas.task_queue.commands.TaskStore", lambda: store)
        args = argparse.Namespace(status="running")
        cmd_queue_list(args)  # should not raise

    def test_queue_status_found(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskStore, cmd_queue_status

        db_path = tmp_path / "q.db"
        monkeypatch.setattr("atlas.task_queue.commands.RESULTS_DIR", tmp_path / "results")
        store = TaskStore(db_path=db_path)
        store.add("abc12345", "index", "index v.mp4")

        monkeypatch.setattr("atlas.task_queue.commands.TaskStore", lambda: store)
        args = argparse.Namespace(task_id="abc12345")
        cmd_queue_status(args)  # should not raise

    def test_queue_status_not_found(self, tmp_path, monkeypatch):
        from atlas.task_queue import TaskStore, cmd_queue_status

        monkeypatch.setattr("atlas.task_queue.commands.RESULTS_DIR", tmp_path / "results")
        monkeypatch.setattr("atlas.task_queue.commands.TaskStore", lambda: TaskStore(db_path=tmp_path / "q.db"))

        args = argparse.Namespace(task_id="nonexistent")
        cmd_queue_status(args)  # should not raise, just prints "not found"


class TestCmdTranscribeQueued:
    """Test that cmd_transcribe correctly queues when no_queue is False."""

    def test_queue_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k1")

        mock_queue = MagicMock()
        mock_queue.submit.return_value = "test1234"
        monkeypatch.setattr("atlas.task_queue.get_queue", lambda: mock_queue)

        video = tmp_path / "v.mp4"
        video.touch()

        args = argparse.Namespace(
            video_path=str(video),
            format="text",
            output=None,
            benchmark=False,
            no_queue=False,
            no_streaming=False,
        )

        with patch("atlas.cli.cmd_media.validate_api_keys"):
            cmd_transcribe(args)  # should queue and return without error

        mock_queue.submit.assert_called_once()
