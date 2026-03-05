from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Path to the pre-built Svelte web UI assets.
# In a development tree the build output lives at ``src/ui/`` (sibling of the
# ``atlas`` package); when the wheel is installed the ``ui/`` directory is
# packaged as a top-level data directory next to the ``atlas`` package in
# site-packages.
_UI_DIR = Path(__file__).resolve().parent.parent / "ui"


class _SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for any unmatched path.

    This is required for a history-mode SPA (e.g. Svelte with client-side
    routing) so that refreshing or deep-linking to ``/ui/dashboard`` serves
    the same ``index.html`` entry-point instead of a 404.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:
            # Any path that doesn't correspond to a real file falls back to the
            # SPA entry-point so the client-side router can take over.
            return FileResponse(_UI_DIR / "index.html")


def ui_router(app: FastAPI) -> None:
    """Mount the pre-built Svelte web UI at /ui if the assets directory exists."""
    if not _UI_DIR.exists():
        return

    # Serve the SPA index.html for the bare /ui path.
    @app.get("/ui", include_in_schema=False)
    def ui_root() -> FileResponse:
        return FileResponse(_UI_DIR / "index.html")

    # Mount all static assets under /ui/.
    app.mount("/ui", _SPAStaticFiles(directory=str(_UI_DIR), html=True), name="ui")
