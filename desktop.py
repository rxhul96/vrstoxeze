"""Nifty Analyzer desktop — native window for the Command Desk.

Double-click / Start Menu starts the local signal-only server and opens
the terminal. Use --client to attach to an already-running server (Docker).

Never places, modifies, or cancels broker orders.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from urllib.request import urlopen

from backend import __version__
from backend.paths import user_data_dir

DEFAULT_URL = os.environ.get("ANALYZER_URL", "http://127.0.0.1:8000")
TITLE = "Nifty Analyzer — SIGNAL-ONLY COMMAND DESK"


def _redirect_stdio() -> None:
    """Keep a log when launched windowed (pythonw / PyInstaller --noconsole)."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    logdir = user_data_dir()
    try:
        logf = open(logdir / "app.log", "a", buffering=1, encoding="utf-8")
    except OSError:
        logf = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = logf
    if sys.stderr is None:
        sys.stderr = logf


def wait_up(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(url + "/api/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def start_embedded(host: str, port: int) -> threading.Thread:
    import uvicorn
    from backend.main import app

    def run() -> None:
        uvicorn.run(app, host=host, port=port, log_level="info")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def open_window(url: str) -> None:
    try:
        import webview  # type: ignore
        webview.create_window(TITLE, url, width=1440, height=900)
        webview.start()
        return
    except Exception as exc:
        print(f"pywebview unavailable ({exc}); opening in the browser")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass


def main() -> None:
    _redirect_stdio()
    p = argparse.ArgumentParser(description=TITLE)
    p.add_argument("--url", default=DEFAULT_URL, help="Always-on server URL")
    p.add_argument("--client", action="store_true", help="Visualization only; do not start uvicorn")
    p.add_argument("--serve", action="store_true", help="Embed FastAPI on this PC")
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    p.add_argument("--check", action="store_true", help="Boot server headlessly and exit")
    args = p.parse_args()

    # Installed / double-click default: run the local server + window.
    embed = (args.serve or (not args.client and not args.check)) or args.check
    if args.client:
        embed = False
    url = args.url if args.client else f"http://{args.host}:{args.port}"

    if embed:
        os.environ.setdefault("MARKET_DATA_MODE", os.environ.get("MARKET_DATA_MODE", "replay"))
        print(f"Nifty Analyzer {__version__} — SIGNAL-ONLY MODE")
        start_embedded(args.host, args.port)
        if not wait_up(url):
            print("Server failed to start", file=sys.stderr)
            sys.exit(1)
        if args.check:
            print("ok", url)
            return

    if args.client and not wait_up(url, timeout=5):
        print(f"Server not reachable at {url}. Start Docker/compose or omit --client.", file=sys.stderr)
        sys.exit(2)

    open_window(url)


if __name__ == "__main__":
    main()
