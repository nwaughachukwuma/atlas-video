"""Tests for atlas.server — endpoint signatures, dispatch, and HTTP methods."""

# ruff: noqa: D102

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from atlas.server import create_app


class TestHealthEndpoints:
    def test_health(self):
        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSearchEndpoint:
    """/search calls the data layer directly and returns structured JSON."""

    def test_search_single_video(self):
        fake_result = MagicMock()
        fake_result.model_dump.return_value = {"segment_id": "seg1", "score": 0.9, "text": "hello"}

        with patch("atlas.vector_store.video_index.search_video", new=AsyncMock(return_value=[fake_result])):
            client = TestClient(create_app())
            resp = client.post("/search", json={"video_id": "vid1", "query": "hello world", "top_k": 3})

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["results"][0]["segment_id"] == "seg1"

    def test_search_all_videos(self):
        with patch("atlas.vector_store.video_index.search_video", new=AsyncMock(return_value=[])):
            client = TestClient(create_app())
            resp = client.post("/search", json={"query": "hello", "top_k": 5})

        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestChatEndpoint:
    """/chat streams SSE chunks from the data layer."""

    def test_chat_streams_sse(self):
        async def fake_chat(video_id, query):
            yield "Hello "
            yield "world"

        with patch("atlas.chat_handler.chat_with_video", side_effect=fake_chat):
            client = TestClient(create_app())
            resp = client.post("/chat", json={"video_id": "vid1", "query": "What is this?"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = [line for line in resp.text.splitlines()]
        assert events[0] == "Hello world"


class TestListVideosEndpoint:
    """/list-videos calls the data layer directly."""

    def test_list_videos_returns_structured_json(self):
        fake_video = MagicMock()
        fake_video.model_dump.return_value = {"video_id": "vid1", "title": "Test"}

        fake_index = MagicMock()
        fake_index.list_videos.return_value = [fake_video]

        with patch("atlas.vector_store.video_index.default_video_index", return_value=fake_index):
            client = TestClient(create_app())
            resp = client.get("/list-videos")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["videos"][0]["video_id"] == "vid1"

    def test_list_videos_empty(self):
        fake_index = MagicMock()
        fake_index.list_videos.return_value = []

        with patch("atlas.vector_store.video_index.default_video_index", return_value=fake_index):
            client = TestClient(create_app())
            resp = client.get("/list-videos")

        assert resp.status_code == 200
        assert resp.json() == {"count": 0, "videos": []}


class TestListChatEndpoint:
    """/list-chat/{video_id} calls the data layer directly."""

    def test_list_chat_returns_history(self):
        fake_chat = MagicMock()
        fake_chat.get_history.return_value = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]

        with patch("atlas.vector_store.video_chat.default_video_chat", return_value=fake_chat):
            client = TestClient(create_app())
            resp = client.get("/list-chat/vid1", params={"last_n": 5})

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert len(body["messages"]) == 2
        # confirm last_n is forwarded
        fake_chat.get_history.assert_called_once_with("vid1", last_n=5)


class TestStatsEndpoint:
    """/stats calls both data stores and returns all stat keys."""

    def test_stats_returns_all_keys(self):
        fake_index = MagicMock()
        fake_index.col_path = "/tmp/vi"
        fake_index.stats = "3 videos"
        fake_index.list_videos.return_value = ["a", "b", "c"]

        fake_chat = MagicMock()
        fake_chat.col_path = "/tmp/vc"
        fake_chat.stats = "10 messages"

        with (
            patch("atlas.vector_store.video_index.default_video_index", return_value=fake_index),
            patch("atlas.vector_store.video_chat.default_video_chat", return_value=fake_chat),
        ):
            client = TestClient(create_app())
            resp = client.get("/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["video_col_path"] == "/tmp/vi"
        assert body["chat_col_path"] == "/tmp/vc"
        assert body["videos_indexed"] == 3
        assert "video_index_stats" in body
        assert "chat_index_stats" in body


class TestGetVideoEndpoint:
    """/get-video/{video_id} calls the data layer and returns data or 404."""

    def test_get_video_found(self):
        fake_index = MagicMock()
        fake_index.get_video_data.return_value = {"title": "My Video", "duration": 120}

        with patch("atlas.vector_store.video_index.default_video_index", return_value=fake_index):
            client = TestClient(create_app())
            resp = client.get("/get-video/vid1")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["title"] == "My Video"

    def test_get_video_not_found(self):
        fake_index = MagicMock()
        fake_index.get_video_data.return_value = None

        with patch("atlas.vector_store.video_index.default_video_index", return_value=fake_index):
            client = TestClient(create_app())
            resp = client.get("/get-video/missing")

        assert resp.status_code == 404


class TestQueueListEndpoint:
    """/queue/list calls TaskStore.list_all and returns structured JSON."""

    def test_queue_list_no_filter(self):
        fake_store = MagicMock()
        fake_store.list_all.return_value = [{"task_id": "t1", "status": "pending"}]

        with patch("atlas.task_queue.store.TaskStore", return_value=fake_store):
            client = TestClient(create_app())
            resp = client.get("/queue/list")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status_filter"] is None
        assert body["count"] == 1
        assert body["tasks"][0]["task_id"] == "t1"

    def test_queue_list_with_status_filter(self):
        fake_store = MagicMock()
        fake_store.list_all.return_value = []

        with patch("atlas.task_queue.store.TaskStore", return_value=fake_store):
            client = TestClient(create_app())
            resp = client.get("/queue/list", params={"status": "running"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["status_filter"] == "running"
        assert body["count"] == 0
        fake_store.list_all.assert_called_once_with("running")


class TestQueueStatusEndpoint:
    """/queue/status/{task_id} returns task details or 404."""

    def test_queue_status_found_no_output(self):
        fake_store = MagicMock()
        fake_store.get.return_value = {
            "task_id": "abc123",
            "status": "completed",
            "started_at": "2024-01-01T00:00:00",
            "finished_at": "2024-01-01T00:01:00",
        }

        with (
            patch("atlas.task_queue.store.TaskStore", return_value=fake_store),
            patch("atlas.task_queue.commands._duration_str", return_value="60.0s"),
            patch("atlas.task_queue.commands._parse_benchmark_file", return_value=[]),
            patch("atlas.task_queue.config.RESULTS_DIR") as mock_dir,
        ):
            # No output.json or benchmark.txt on disk
            mock_results_dir = MagicMock()
            mock_dir.__truediv__ = lambda self, x: mock_results_dir
            mock_results_dir.__truediv__ = lambda self, x: MagicMock(exists=MagicMock(return_value=False))

            client = TestClient(create_app())
            resp = client.get("/queue/status/abc123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "abc123"
        assert body["status"] == "completed"

    def test_queue_status_not_found(self):
        fake_store = MagicMock()
        fake_store.get.return_value = None

        with patch("atlas.task_queue.store.TaskStore", return_value=fake_store):
            client = TestClient(create_app())
            resp = client.get("/queue/status/missing")

        assert resp.status_code == 404


class TestMediaPostEndpoints:
    """extract/index/transcribe use _run_command; JSON stdout is auto-parsed."""

    def test_extract_no_queue_returns_json(self, monkeypatch):
        """When --no-queue, cmd_extract prints JSON to stdout; server returns it parsed."""
        from atlas import server as server_module

        def fake_extract(args):
            print(json.dumps({"video_path": args.video_path, "segments_count": 5, "video_descriptions": []}))

        monkeypatch.setattr(server_module, "cmd_extract", fake_extract)
        client = TestClient(create_app())
        resp = client.post("/extract", json={"video_path": "/data/v.mp4", "no_queue": True})

        assert resp.status_code == 200
        body = resp.json()
        assert body["video_path"] == "/data/v.mp4"
        assert body["segments_count"] == 5

    def test_transcribe_no_queue_returns_json(self, monkeypatch):
        from atlas import server as server_module

        def fake_transcribe(args):
            print(json.dumps({"transcript": "Hello world", "format": args.format, "video_path": args.video_path}))

        monkeypatch.setattr(server_module, "cmd_transcribe", fake_transcribe)
        client = TestClient(create_app())
        resp = client.post("/transcribe", json={"video_path": "/data/v.mp4", "no_queue": True, "format": "text"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["transcript"] == "Hello world"
        assert body["format"] == "text"

    def test_index_no_queue_returns_json(self, monkeypatch):
        from atlas import server as server_module

        def fake_index(args):
            print(json.dumps({"video_id": "vid1", "video_path": args.video_path, "indexed_count": 10}))

        monkeypatch.setattr(server_module, "cmd_index", fake_index)
        client = TestClient(create_app())
        resp = client.post("/index", json={"video_path": "/data/v.mp4", "no_queue": True})

        assert resp.status_code == 200
        body = resp.json()
        assert body["video_id"] == "vid1"
        assert body["indexed_count"] == 10

    def test_extract_queued_returns_command_result(self, monkeypatch):
        """When queued, output is text confirmation; server wraps it in CommandResult."""
        from atlas import server as server_module

        def fake_extract(args):
            print("Task queued: abc-123")

        monkeypatch.setattr(server_module, "cmd_extract", fake_extract)
        client = TestClient(create_app())
        resp = client.post("/extract", json={"video_path": "/data/v.mp4"})

        assert resp.status_code == 200
        body = resp.json()
        # Non-JSON stdout falls back to CommandResult shape
        assert body["ok"] is True
        assert "Task queued" in body["output"]

    def test_extract_defaults_preserved(self, monkeypatch):
        from atlas import server as server_module

        captured: dict[str, Any] = {}

        def fake_extract(args):
            captured.update(vars(args))
            print("done")

        monkeypatch.setattr(server_module, "cmd_extract", fake_extract)
        client = TestClient(create_app())
        client.post("/extract", json={"video_path": "/data/v.mp4"})

        assert captured["chunk_duration"] == "15s"
        assert captured["overlap"] == "1s"
        assert captured["no_queue"] is False
