"""CLI handler for running the Atlas HTTP server."""

from __future__ import annotations

import argparse


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the Atlas HTTP server."""
    import uvicorn

    from ..server import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
