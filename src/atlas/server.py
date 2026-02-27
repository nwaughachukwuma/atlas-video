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
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .cli.cmd_explore import cmd_chat, cmd_get_data, cmd_list_chat, cmd_list_videos, cmd_search, cmd_stats
from .cli.cmd_media import cmd_extract, cmd_index, cmd_transcribe
from .task_queue.commands import cmd_queue_list, cmd_queue_status


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
    search_args: list[str]
    top_k: int = 10


class ChatRequest(BaseModel):
    video_id: str
    query: str


def _run_command(func, args: argparse.Namespace) -> CommandResult:
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

    return CommandResult(ok=True, output=stdout.getvalue(), error=stderr.getvalue())


def _ns(model: BaseModel) -> argparse.Namespace:
    return argparse.Namespace(**model.model_dump())


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Server", version="0.1.2")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/extract", response_model=CommandResult)
    def extract(payload: ExtractRequest) -> CommandResult:
        return _run_command(cmd_extract, _ns(payload))

    @app.post("/index", response_model=CommandResult)
    def index(payload: IndexRequest) -> CommandResult:
        return _run_command(cmd_index, _ns(payload))

    @app.post("/transcribe", response_model=CommandResult)
    def transcribe(payload: TranscribeRequest) -> CommandResult:
        return _run_command(cmd_transcribe, _ns(payload))

    @app.post("/search", response_model=CommandResult)
    def search(payload: SearchRequest) -> CommandResult:
        return _run_command(cmd_search, _ns(payload))

    @app.post("/chat", response_model=CommandResult)
    def chat(payload: ChatRequest) -> CommandResult:
        return _run_command(cmd_chat, _ns(payload))

    @app.get("/list-videos", response_model=CommandResult)
    def list_videos() -> CommandResult:
        return _run_command(cmd_list_videos, argparse.Namespace(benchmark=False))

    @app.get("/list-chat/{video_id}", response_model=CommandResult)
    def list_chat(video_id: str, last_n: int = 20) -> CommandResult:
        return _run_command(cmd_list_chat, argparse.Namespace(video_id=video_id, last_n=last_n))

    @app.get("/stats", response_model=CommandResult)
    def stats() -> CommandResult:
        return _run_command(cmd_stats, argparse.Namespace(benchmark=False))

    @app.get("/get-video/{video_id}", response_model=CommandResult)
    def get_video(video_id: str) -> CommandResult:
        return _run_command(cmd_get_data, argparse.Namespace(video_id=video_id, output=None))

    @app.get("/queue/list", response_model=CommandResult)
    def queue_list(
        status: Literal["pending", "running", "completed", "failed", "timeout"] | None = None,
    ) -> CommandResult:
        return _run_command(cmd_queue_list, argparse.Namespace(status=status))

    @app.get("/queue/status/{task_id}", response_model=CommandResult)
    def queue_status(task_id: str) -> CommandResult:
        return _run_command(cmd_queue_status, argparse.Namespace(task_id=task_id))

    return app
