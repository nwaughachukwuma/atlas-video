"""Tests for atlas.server — endpoint signatures, dispatch, and HTTP methods."""

# ruff: noqa: D102

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.server import create_app


class TestHealthEndpoints:
    def test_health(self):
        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestPostEndpoints:
    """POST endpoints that accept JSON bodies — extract, index, transcribe, search, chat."""

    def test_search_dispatches_correct_fields(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called["search_args"] = args.search_args
            called["top_k"] = args.top_k
            # Verify no phantom flags leaked in
            assert not hasattr(args, "no_queue")
            assert not hasattr(args, "no_streaming")
            print("ok")

        monkeypatch.setattr(server_module, "cmd_search", fake)
        client = TestClient(create_app())
        resp = client.post("/search", json={"search_args": ["hello world"], "top_k": 3})

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert called["search_args"] == ["hello world"]
        assert called["top_k"] == 3

    def test_chat_dispatches_correct_fields(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called["video_id"] = args.video_id
            called["query"] = args.query
            assert not hasattr(args, "no_queue")
            assert not hasattr(args, "no_streaming")
            print("reply")

        monkeypatch.setattr(server_module, "cmd_chat", fake)
        client = TestClient(create_app())
        resp = client.post("/chat", json={"video_id": "vid1", "query": "What is this?"})

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert called["video_id"] == "vid1"
        assert called["query"] == "What is this?"

    def test_extract_dispatches_all_flags(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called.update(vars(args))
            print("extracted")

        monkeypatch.setattr(server_module, "cmd_extract", fake)
        client = TestClient(create_app())
        resp = client.post("/extract", json={"video_path": "/data/v.mp4", "no_queue": True})

        assert resp.status_code == 200
        assert called["video_path"] == "/data/v.mp4"
        assert called["no_queue"] is True
        assert called["chunk_duration"] == "15s"  # default preserved


class TestGetEndpoints:
    """GET endpoints — list-videos, stats, list-chat, get-video, queue."""

    def test_list_videos_is_get_no_body(self, monkeypatch):
        from atlas import server as server_module

        def fake(args):
            print("videos")

        monkeypatch.setattr(server_module, "cmd_list_videos", fake)
        client = TestClient(create_app())
        resp = client.get("/list-videos")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_stats_is_get_no_body(self, monkeypatch):
        from atlas import server as server_module

        def fake(args):
            print("stats")

        monkeypatch.setattr(server_module, "cmd_stats", fake)
        client = TestClient(create_app())
        resp = client.get("/stats")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_list_chat_uses_path_and_query(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called["video_id"] = args.video_id
            called["last_n"] = args.last_n
            print("chat history")

        monkeypatch.setattr(server_module, "cmd_list_chat", fake)
        client = TestClient(create_app())
        resp = client.get("/list-chat/vid1", params={"last_n": 5})

        assert resp.status_code == 200
        assert called["video_id"] == "vid1"
        assert called["last_n"] == 5

    def test_get_video_uses_path_param(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called["video_id"] = args.video_id
            assert args.output is None
            print("{}")

        monkeypatch.setattr(server_module, "cmd_get_data", fake)
        client = TestClient(create_app())
        resp = client.get("/get-video/vid1")

        assert resp.status_code == 200
        assert called["video_id"] == "vid1"

    def test_queue_status_uses_path_param(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called["task_id"] = args.task_id
            print("queued")

        monkeypatch.setattr(server_module, "cmd_queue_status", fake)
        client = TestClient(create_app())
        resp = client.get("/queue/status/abc123")

        assert resp.status_code == 200
        assert called["task_id"] == "abc123"

    def test_queue_list_accepts_status_query(self, monkeypatch):
        from atlas import server as server_module

        called = {}

        def fake(args):
            called["status"] = args.status
            print("listed")

        monkeypatch.setattr(server_module, "cmd_queue_list", fake)
        client = TestClient(create_app())
        resp = client.get("/queue/list", params={"status": "running"})

        assert resp.status_code == 200
        assert called["status"] == "running"
