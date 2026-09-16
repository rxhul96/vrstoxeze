"""Nifty Institutional Command Desk — visualization client.

Does not start Kite. Does not place orders. Optionally embeds uvicorn for
laptop-only days; production points ANALYZER_URL at the always-on server.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from urllib.request import urlopen

DEFAULT_URL = os.environ.get("ANALYZER_URL", "http://127.0.0.1:8000")


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
        webview.create_window(
            "NIFTY INSTITUTIONAL COMMAND DESK — SIGNAL-ONLY",
            url,
            width=1440,
            height=900,
        )
        webview.start()
    except Exception:
        webbrowser.open(url)
        print(f"Opened {url} (install pywebview for a native window)")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL, help="Always-on server URL")
    p.add_argument("--client", action="store_true", help="Never embed uvicorn; visualization only")
    p.add_argument("--serve", action="store_true", help="Embed FastAPI on this PC (dev / laptop-only)")
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    p.add_argument("--check", action="store_true", help="Boot server headlessly and exit")
    args = p.parse_args()

    embed = args.serve and not args.client
    url = args.url if args.client or not embed else f"http://{args.host}:{args.port}"

    if embed or args.check:
        os.environ.setdefault("MARKET_DATA_MODE", os.environ.get("MARKET_DATA_MODE", "replay"))
        start_embedded(args.host, args.port)
        if not wait_up(url):
            print("Server failed to start", file=sys.stderr)
            sys.exit(1)
        if args.check:
            print("ok", url)
            return

    if args.client and not wait_up(url, timeout=5):
        print(f"Server not reachable at {url}. Start Docker/compose first.", file=sys.stderr)
        sys.exit(2)

    open_window(url)


if __name__ == "__main__":
    main()
