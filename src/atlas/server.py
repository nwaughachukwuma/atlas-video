"""Atlas HTTP server that exposes CLI actions as JSON endpoints.

Design rules
------------
* Every request model only contains fields the underlying CLI handler actually
  reads from ``argparse.Namespace``.  No phantom flags.
* Read-only / side-effect-free endpoints use **GET** (with path / query params).
* Mutating / long-running endpoints use **POST** (with a JSON body).
* Endpoints that accept a video file use **multipart/form-data** so that
  clients can upload files from any device — no shared filesystem needed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ._meta import DISPLAY_NAME, __version__
from .cli.cmd_media import cmd_extract, cmd_index, cmd_transcribe
from .file_extension import get_ext_from_mimetype
from .ui_router import ui_router
from .uuid import uuid


class CommandResult(BaseModel):
    ok: bool
    output: str
    error: str


class SearchRequest(BaseModel):
    query: str
    video_id: str | None = None
    top_k: int = 10


class ChatRequest(BaseModel):
    video_id: str
    query: str


def _save_upload(upload: UploadFile) -> Path:
    """Persist an uploaded file to a temp directory and return its path.

    The caller is responsible for cleaning up the parent directory
    (``path.parent``) when processing is complete.
    """
    suffix = (
        get_ext_from_mimetype(upload.content_type)
        if upload.content_type
        else Path(upload.filename).suffix
        if upload.filename
        else ".mp4"
    )

    tmp_dir = Path(tempfile.mkdtemp(prefix="atlas_upload_"))
    dest = tmp_dir / f"upload_{uuid(10)}_{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def _run_command(func, args: argparse.Namespace, *, tmp_dir: Path | None = None) -> Any:
    """Run a CLI handler capturing stdout/stderr.

    Used only for mutating/queuing commands (extract, index, transcribe) whose
    output is either queued-task confirmation text or JSON (when --no-queue).
    When stdout is valid JSON it is parsed and returned directly so the client
    gets structured data rather than an escaped string.

    If *tmp_dir* is supplied the directory is removed after the handler returns,
    regardless of success or failure.
    """
    from rich.console import Console

    from . import cli as cli_module

    stdout = StringIO()
    stderr = StringIO()

    # Force the shared CLI console to write to our stderr buffer so that Rich
    # progress bars / spinners don't pollute stdout (which we parse as JSON).
    cli_module._console = Console(file=stderr)
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                func(args)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
                http_status = 500 if code == 1 else 400
                raise HTTPException(
                    http_status,
                    detail={
                        "ok": False,
                        "exit_code": code,
                        "output": stdout.getvalue(),
                        "error": stderr.getvalue(),
                    },
                ) from exc
    finally:
        cli_module._console = None
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    raw = stdout.getvalue()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return CommandResult(ok=True, output=raw, error=stderr.getvalue())


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(title=f"{DISPLAY_NAME} Server", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_execution_time_header(request, call_next):
        started = perf_counter()
        response = await call_next(request)
        elapsed_ms = (perf_counter() - started) * 1000
        response.headers["x-execution-time"] = f"{elapsed_ms:.3f}ms"

        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # ── mutating / long-running (POST with file upload) ─────────────

    @app.post("/extract")
    def extract(
        video: UploadFile = File(..., description="Video file to process"),
        chunk_duration: str = Form("15s"),
        overlap: str = Form("1s"),
        attrs: str | None = Form(None, description="Comma-separated description attributes"),
        output: str | None = Form(None),
        format: Literal["json", "text"] = Form("text"),
        include_summary: bool = Form(True),
        benchmark: bool = Form(False),
        no_queue: bool = Form(True),
        no_streaming: bool = Form(True),
    ):
        saved = _save_upload(video)
        args = argparse.Namespace(
            video_path=str(saved),
            chunk_duration=chunk_duration,
            overlap=overlap,
            attrs=attrs.split(",") if attrs else None,
            output=output,
            format=format,
            include_summary=include_summary,
            benchmark=benchmark,
            no_queue=no_queue,
            no_streaming=no_streaming,
        )
        return _run_command(cmd_extract, args, tmp_dir=saved.parent)

    @app.post("/index")
    def index(
        video: UploadFile = File(..., description="Video file to process"),
        chunk_duration: str = Form("15s"),
        overlap: str = Form("1s"),
        attrs: str | None = Form(None, description="Comma-separated description attributes"),
        include_summary: bool = Form(True),
        benchmark: bool = Form(False),
        no_queue: bool = Form(True),
        no_streaming: bool = Form(True),
    ) -> Any:
        saved = _save_upload(video)
        args = argparse.Namespace(
            video_path=str(saved),
            chunk_duration=chunk_duration,
            overlap=overlap,
            attrs=attrs.split(",") if attrs else None,
            include_summary=include_summary,
            benchmark=benchmark,
            no_queue=no_queue,
            no_streaming=no_streaming,
        )
        return _run_command(cmd_index, args, tmp_dir=saved.parent)

    @app.post("/transcribe")
    def transcribe(
        video: UploadFile = File(..., description="Video file to process"),
        format: Literal["text", "vtt", "srt"] = Form("text"),
        output: str | None = Form(None),
        benchmark: bool = Form(False),
        no_queue: bool = Form(True),
        no_streaming: bool = Form(True),
    ) -> Any:
        saved = _save_upload(video)
        args = argparse.Namespace(
            video_path=str(saved),
            format=format,
            output=output,
            benchmark=benchmark,
            no_queue=no_queue,
            no_streaming=no_streaming,
        )
        return _run_command(cmd_transcribe, args, tmp_dir=saved.parent)

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
        from .task_queue.commands import _duration_str
        from .task_queue.config import RESULTS_DIR
        from .task_queue.store import TaskStore

        store = TaskStore()
        task = store.get(task_id)
        if not task:
            raise HTTPException(404, detail=f"Task {task_id} not found")

        output: dict[str, Any] = dict(task)
        output["duration"] = _duration_str(task.get("started_at"), task.get("finished_at")) or None

        results_dir = RESULTS_DIR / task_id
        output_file = results_dir / "output.json"
        benchmark_file = results_dir / "benchmark.txt"

        if output_file.exists():
            output["output_path"] = str(output_file)

        if benchmark_file.exists():
            output["benchmark_path"] = str(benchmark_file)

        return output

    ui_router(app)
    return app
