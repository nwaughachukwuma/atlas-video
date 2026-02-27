"""Atlas HTTP server that exposes CLI actions as JSON endpoints.

Design rules
------------
* Every request model only contains fields the underlying CLI handler actually
  reads from ``argparse.Namespace``.  No phantom flags.
* Read-only / side-effect-free endpoints use **GET** (with path / query params).
* Mutating / long-running endpoints use **POST** (with a JSON body).
"""

from __future__ import annotations

import argparse
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .cli.cmd_media import cmd_extract, cmd_index, cmd_transcribe


class CommandResult(BaseModel):
    ok: bool
    output: str
    error: str


class ExtractRequest(BaseModel):
    video_path: str
    chunk_duration: str = "15s"
    overlap: str = "1s"
    attrs: list[str] | None = None
    output: str | None = None
    format: Literal["json", "text"] = "text"
    include_summary: bool = True
    benchmark: bool = False
    no_queue: bool = False
    no_streaming: bool = False


class IndexRequest(BaseModel):
    video_path: str
    chunk_duration: str = "15s"
    overlap: str = "0s"
    embedding_dim: int = 768
    attrs: list[str] | None = None
    include_summary: bool = True
    benchmark: bool = False
    no_queue: bool = False
    no_streaming: bool = False


class TranscribeRequest(BaseModel):
    video_path: str
    format: Literal["text", "vtt", "srt"] = "text"
    output: str | None = None
    benchmark: bool = False
    no_queue: bool = False
    no_streaming: bool = False


class SearchRequest(BaseModel):
    query: str
    video_id: str | None = None
    top_k: int = 10


class ChatRequest(BaseModel):
    video_id: str
    query: str


def _run_command(func, args: argparse.Namespace) -> Any:
    """Run a CLI handler capturing stdout/stderr.

    Used only for mutating/queuing commands (extract, index, transcribe) whose
    output is either queued-task confirmation text or JSON (when --no-queue).
    When stdout is valid JSON it is parsed and returned directly so the client
    gets structured data rather than an escaped string.
    """
    from . import cli as cli_module

    stdout = StringIO()
    stderr = StringIO()

    cli_module._console = None
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            func(args)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "exit_code": code,
                    "output": stdout.getvalue(),
                    "error": stderr.getvalue(),
                },
            ) from exc

    raw = stdout.getvalue()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return CommandResult(ok=True, output=raw, error=stderr.getvalue())


def _ns(model: BaseModel) -> argparse.Namespace:
    return argparse.Namespace(**model.model_dump())


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Server", version="0.1.2")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # ── mutating / long-running (POST) ────────────────────────────────

    @app.post("/extract")
    def extract(payload: ExtractRequest) -> Any:
        return _run_command(cmd_extract, _ns(payload))

    @app.post("/index")
    def index(payload: IndexRequest) -> Any:
        return _run_command(cmd_index, _ns(payload))

    @app.post("/transcribe")
    def transcribe(payload: TranscribeRequest) -> Any:
        return _run_command(cmd_transcribe, _ns(payload))

    # ── search — calls data layer directly, returns structured JSON ────

    @app.post("/search")
    async def search(payload: SearchRequest) -> dict[str, Any]:
        from .vector_store.video_index import search_video

        video_id = payload.video_id
        query = payload.query
        results = await search_video(query, payload.top_k, video_id)
        return {
            "count": len(results),
            "results": [r.model_dump() for r in results],
        }

    # ── chat — SSE stream ─────────────────────────────────────────────

    @app.post("/chat")
    async def chat(payload: ChatRequest) -> StreamingResponse:
        from .chat_handler import chat_with_video

        generator = chat_with_video(payload.video_id, payload.query)
        return StreamingResponse(generator, media_type="text/event-stream")

    @app.get("/list-videos")
    def list_videos() -> dict[str, Any]:
        from .vector_store.video_index import default_video_index

        vi = default_video_index()
        videos = vi.list_videos()
        return {
            "count": len(videos),
            "videos": [v.model_dump() for v in videos],
        }

    @app.get("/list-chat/{video_id}")
    def list_chat(video_id: str, last_n: int = 20) -> dict[str, Any]:
        from .vector_store.video_chat import default_video_chat

        vc = default_video_chat()
        history = vc.get_history(video_id, last_n=last_n)
        return {
            "count": len(history),
            "messages": history,
        }

    @app.get("/stats")
    def stats() -> dict[str, Any]:
        from .vector_store.video_chat import default_video_chat
        from .vector_store.video_index import default_video_index

        vi = default_video_index()
        vc = default_video_chat()
        return {
            "video_col_path": str(vi.col_path),
            "video_index_stats": str(vi.stats),
            "chat_col_path": str(vc.col_path),
            "chat_index_stats": str(vc.stats),
            "videos_indexed": len(vi.list_videos()),
        }

    @app.get("/get-video/{video_id}")
    def get_video(video_id: str) -> dict[str, Any]:
        from .vector_store.video_index import default_video_index

        vi = default_video_index()
        data = vi.get_video_data(video_id)
        if not data:
            raise HTTPException(status_code=404, detail=f"No data found for video_id={video_id}")
        return {"data": data}

    @app.get("/queue/list")
    def queue_list(
        status: Literal["pending", "running", "completed", "failed", "timeout"] | None = None,
    ) -> dict[str, Any]:
        from .task_queue.store import TaskStore

        store = TaskStore()
        tasks = store.list_all(status)
        return {
            "status_filter": status,
            "count": len(tasks),
            "tasks": tasks,
        }

    @app.get("/queue/status/{task_id}")
    def queue_status(task_id: str) -> dict[str, Any]:
        from .task_queue.commands import _duration_str, _parse_benchmark_file
        from .task_queue.config import RESULTS_DIR
        from .task_queue.store import TaskStore

        store = TaskStore()
        task = store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        output: dict[str, Any] = dict(task)
        output["duration"] = _duration_str(task.get("started_at"), task.get("finished_at")) or None

        results_dir = RESULTS_DIR / task_id
        output_file = results_dir / "output.json"
        benchmark_file = results_dir / "benchmark.txt"

        if output_file.exists():
            try:
                output["result"] = json.loads(output_file.read_text())
            except Exception:
                output["result"] = output_file.read_text()

        if benchmark_file.exists():
            rows = _parse_benchmark_file(benchmark_file)
            output["benchmark"] = [
                {"function": r[0], "calls": r[1], "total_s": r[2], "avg_s": r[3], "min_s": r[4], "max_s": r[5]}
                for r in rows
            ]

        return output

    return app
