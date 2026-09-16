"""Nifty Institutional Command Desk — FastAPI intelligence server.

Signal-only. No order endpoints. Desktop is a visualization client.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.agents.desk import FORBIDDEN_TOOLS
from backend.config import get_settings
from backend.paths import frontend_dir
from backend.feed.bus import MarketBus
from backend.feed.kite import KiteLiveFeed
from backend.feed.replay import session_tape
from backend.health import build as build_health
from backend.analytics.news import collect_news
from backend.market import now_ist, session_state
from backend.pipeline import DeskPipeline
from backend.safety.trading_disabled import TRADING_EXECUTION_ENABLED, refuse_execution
from backend.session.runner import SessionRunner
from backend.signals.paper_track import grade
from backend.storage.db import get_store

log = logging.getLogger("nifty")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

FRONTEND = frontend_dir()


class Hub:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.store = get_store()
        self.bus = MarketBus()
        self.pipeline = DeskPipeline()
        self.runner = SessionRunner(self.store, kite_ok=self._kite_ok)
        self.kite = KiteLiveFeed(self.bus)
        self.ws_clients: set[WebSocket] = set()
        self.last_ts = 0.0
        self.kite_ok = False
        self._tasks: list[asyncio.Task] = []

    def _kite_ok(self) -> bool:
        if self.settings.is_replay:
            return True
        return bool(self.settings.kite_configured)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in list(self.ws_clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)

    def persist(self, snapshot: dict) -> None:
        ts = snapshot.get("ts") or datetime.utcnow().isoformat()
        try:
            c = snapshot["candle"]
            self.store.execute(
                "INSERT INTO ticks (ts, instrument, ltp, volume) VALUES (?,?,?,?)",
                (ts, "NIFTY", c["close"], c.get("volume") or 0),
            )
            self.store.insert_candle(
                ts, "NIFTY", "1m", c["open"], c["high"], c["low"], c["close"], c.get("volume") or 0
            )
            self.store.insert_json("option_snapshots", ts, snapshot["chain"])
            self.store.insert_json("oi_snapshots", ts, {"heatmap": snapshot["heatmap"], "flow": snapshot["oi_flow"]})
            self.store.insert_json("cvd_snapshots", ts, snapshot["cvd"])
            self.store.insert_json("pcr_snapshots", ts, snapshot["pcr"])
            self.store.insert_json("ict_events", ts, snapshot["ict"])
            self.store.execute(
                "INSERT INTO market_regime (ts, regime, payload) VALUES (?,?,?)",
                (ts, snapshot["regime"], __import__("json").dumps(snapshot["regime_detail"], default=str)),
            )
            sig = snapshot.get("signal") or {}
            if sig.get("signal_id"):
                self.store.upsert_signal(ts, sig["signal_id"], __import__("json").dumps(sig, default=str))
        except Exception as exc:  # noqa: BLE001
            log.warning("persist failed: %s", exc)

    async def on_bar(self, bar: dict) -> dict:
        snap = self.pipeline.ingest_bar(bar, persist=self.persist, news=self.pipeline.news)
        self.last_ts = datetime.utcnow().timestamp()
        await self.bus.publish(snap)
        await self.broadcast(snap)
        return snap


hub = Hub()


async def replay_loop() -> None:
    day = now_ist().strftime("%Y-%m-%d")
    tape = session_tape(day)
    i = 0
    hub.kite_ok = True
    hub.pipeline.news = collect_news(hub.settings.news_enabled)
    while True:
        phase = hub.runner.tick()
        if hub.settings.is_replay:
            bar = tape[i % len(tape)]
            await hub.on_bar(bar)
            i += 1
            await asyncio.sleep(0.35)
            continue
        if phase.get("collecting"):
            # Live mode: REST poll if ticker is not attached.
            quote = await hub.kite.poll_quotes()
            if quote:
                hub.kite_ok = True
            else:
                hub.kite_ok = hub._kite_ok()
        await asyncio.sleep(1.0)


async def news_loop() -> None:
    while True:
        try:
            hub.pipeline.news = collect_news(hub.settings.news_enabled)
            for item in hub.pipeline.news[:8]:
                hub.store.execute(
                    "INSERT INTO news (ts, source, headline, sentiment, relevance, impact, confidence, payload) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        item.get("timestamp"),
                        item.get("source"),
                        item.get("headline"),
                        item.get("sentiment"),
                        item.get("effective_relevance"),
                        item.get("impact"),
                        item.get("confidence"),
                        __import__("json").dumps(item, default=str),
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("news loop: %s", exc)
        await asyncio.sleep(60)


async def health_loop() -> None:
    while True:
        try:
            payload = build_health(hub)
            hub.store.insert_json("system_health", datetime.utcnow().isoformat(), payload)
        except Exception:
            pass
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert TRADING_EXECUTION_ENABLED is False
    hub.bus.register_kite_connection()
    hub._tasks = [
        asyncio.create_task(replay_loop()),
        asyncio.create_task(news_loop()),
        asyncio.create_task(health_loop()),
    ]
    log.info("Command Desk server up — SIGNAL-ONLY MODE")
    yield
    for t in hub._tasks:
        t.cancel()


app = FastAPI(title="Nifty Institutional Command Desk", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
def api_health():
    return build_health(hub)


@app.get("/api/status")
def api_status():
    return {
        "session": session_state(),
        "runner": hub.runner.last_state,
        "signal_only": True,
        "automated_trading": False,
        "execution_enabled": False,
        "kite_connections": hub.bus.kite_connections,
        "mode": hub.settings.market_data_mode,
    }


@app.get("/api/snapshot")
def api_snapshot():
    snap = hub.pipeline.last_snapshot or {}
    return snap


@app.get("/api/history")
def api_history():
    candles = hub.pipeline.candles[-300:]
    return {"candles": candles}


@app.get("/api/session/replay")
def api_replay(since: str | None = None):
    day = now_ist().strftime("%Y-%m-%d")
    since = since or f"{day}T09:15:00"
    return {
        "since": since,
        "ticks": hub.store.replay("ticks", since)[-2000:],
        "candles": hub.store.replay("candles", since)[-400:],
        "cvd": hub.store.replay("cvd_snapshots", since)[-400:],
        "options": hub.store.replay("option_snapshots", since)[-200:],
        "signals": hub.store.replay("signals", since),
        "news": hub.store.replay("news", since)[-50:],
        "snapshot": hub.pipeline.last_snapshot,
    }


@app.get("/api/signals")
def api_signals():
    return {"current": hub.pipeline.current_signal, "history": hub.store.query("SELECT * FROM signals ORDER BY id DESC LIMIT 50")}


@app.get("/api/signals/paper")
def api_paper():
    rows = hub.store.query("SELECT * FROM paper_signals ORDER BY id DESC LIMIT 50")
    return {"rows": rows, "broker": None}


@app.post("/api/signals/paper/{signal_id}")
def api_paper_grade(signal_id: str):
    """Grade a stored signal from later candles. No broker call."""
    rows = hub.store.query("SELECT payload FROM signals WHERE signal_id = ?", (signal_id,))
    if not rows:
        return JSONResponse({"ok": False, "reason": "unknown signal"}, status_code=404)
    import json
    sig = json.loads(rows[0]["payload"]) if isinstance(rows[0]["payload"], str) else rows[0]["payload"]
    closes = [c["close"] for c in hub.pipeline.candles[-40:]]
    result = grade(sig, closes)
    hub.store.execute(
        "INSERT INTO paper_signals (signal_id, ts, outcome, move_pts, payload) VALUES (?,?,?,?,?)",
        (signal_id, datetime.utcnow().isoformat(), result["outcome"], result["move_pts"], json.dumps(result)),
    )
    return result


@app.get("/api/news")
def api_news():
    return {"items": hub.pipeline.news}


@app.get("/api/oi/chain")
def api_chain():
    return hub.pipeline.last_chain or {}


@app.get("/kite/login")
def kite_login():
    url = hub.kite.login_url()
    if not url:
        return JSONResponse(
            {"ok": False, "reason": "KITE LOGIN REQUIRED — set KITE_API_KEY on the server"},
            status_code=503,
        )
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url)


@app.get("/kite/callback")
def kite_callback(request_token: str = ""):
    """Exchange request token on the server. Desktop never sees the secret."""
    settings = hub.settings
    if not settings.kite_api_key or not settings.kite_api_secret:
        return JSONResponse({"ok": False, "reason": "server missing kite credentials"}, status_code=503)
    try:
        from kiteconnect import KiteConnect  # type: ignore
        from backend.safety.trading_disabled import seal_kite_read_only
        k = seal_kite_read_only(KiteConnect(api_key=settings.kite_api_key))
        data = k.generate_session(request_token, api_secret=settings.kite_api_secret)
        token = data.get("access_token")
        hub.kite.attach_token(token)
        env_path = settings.data_dir / ".kite_token"
        env_path.write_text(token, encoding="utf-8")
        hub.kite_ok = True
        return {"ok": True, "mode": "signal-only"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "reason": str(exc)}, status_code=400)


@app.get("/api/safety")
def api_safety():
    return {
        "execution_enabled": TRADING_EXECUTION_ENABLED,
        "automated_trading": False,
        "signal_only": True,
        "agent_tools": [],
        "forbidden_tools": list(FORBIDDEN_TOOLS),
        "kite_connections": hub.bus.kite_connections,
    }


# Deliberately no POST /api/exec/order, /api/orders, /api/exec/basket.
# If something still hits a guessed path, refuse without generating an order payload.
@app.api_route("/api/exec/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/api/orders", methods=["POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/api/order", methods=["POST", "PUT", "PATCH", "DELETE"])
def _no_execution(rest: str = ""):
    return JSONResponse(refuse_execution("blocked_path"), status_code=404)


@app.websocket("/ws")
async def ws_desk(ws: WebSocket):
    await ws.accept()
    hub.ws_clients.add(ws)
    if hub.pipeline.last_snapshot:
        await ws.send_json(hub.pipeline.last_snapshot)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.ws_clients.discard(ws)
