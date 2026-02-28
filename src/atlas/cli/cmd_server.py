"""
CLI handler for running the Atlas HTTP server
"""

from __future__ import annotations

import argparse


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the Atlas HTTP server."""
    import uvicorn
    from dotenv import load_dotenv

    from ..server import create_app

    if getattr(args, "env_file", None):
        load_dotenv(args.env_file, override=True)

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
