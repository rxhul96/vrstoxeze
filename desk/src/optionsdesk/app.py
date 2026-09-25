"""Standalone FastAPI app: ``uvicorn --factory optionsdesk.app:create_app``.

Serves the API under ``/desk`` and, when the UI has been built (``make ui-build``), the static
panel under ``/`` from ``src/optionsdesk/static``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from optionsdesk import __version__
from optionsdesk.api import build_desk_router
from optionsdesk.config import DeskConfig
from optionsdesk.engine import DeskEngine, build_engine

STATIC_DIR = Path(__file__).parent / "static"


def create_app(engine: DeskEngine | None = None, config: DeskConfig | None = None) -> FastAPI:
    logging.basicConfig(level=os.environ.get("DESK_LOG_LEVEL", "INFO"))
    engine = engine or build_engine(config)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # In live mode without a host tick feed, poll the broker for LTPs so SL/target exits fire.
        stop = asyncio.Event()

        async def poller() -> None:
            while not stop.is_set():
                try:
                    await asyncio.to_thread(engine.poll_prices)
                except Exception as exc:  # pragma: no cover
                    logging.getLogger("optionsdesk.app").warning("poll failed: %s", exc)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=float(os.environ.get("DESK_POLL_SEC", "3")))

        task = asyncio.create_task(poller()) if engine.mode == "live" else None
        yield
        stop.set()
        if task:
            task.cancel()

    app = FastAPI(title="optionsdesk", version=__version__, lifespan=lifespan)
    app.state.desk_engine = engine
    origins = [o for o in os.environ.get("DESK_CORS_ORIGINS", "http://localhost:5173").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(build_desk_router(engine))

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "mode": engine.mode, "version": __version__}

    if STATIC_DIR.is_dir() and (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
    return app
