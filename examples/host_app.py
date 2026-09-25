"""Minimal example of mounting the desk into an existing FastAPI application.

Run: uvicorn examples.host_app:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from optionsdesk import DeskConfig, build_desk_router
from optionsdesk.engine import build_engine
from optionsdesk.models import SignalIn, StrategyStats

app = FastAPI(title="Nifty Analyzer (host)")

desk = build_engine(DeskConfig())
app.state.desk = desk
app.include_router(build_desk_router(desk))


@app.post("/analyzer/demo-signal")
def demo_signal() -> dict:
    """Shows how an in-process analyzer feeds the desk without going over HTTP."""
    rec = desk.submit_signal(
        SignalIn(
            strategy_id="cvd_breakout",
            code_hash="abc123",
            tradingsymbol="NIFTY24SEP25000CE",
            direction="BUY",
            entry=100,
            stop_loss=90,
            target=120,
            confidence=0.82,
            stats=StrategyStats(live_win_rate=0.74, live_trades=31, oos_sharpe=1.7),
        )
    )
    return rec.model_dump(mode="json")


def on_ticks(ticks: list[dict]) -> None:
    """Wire this to the Kite ticker callback so SL/target exits fire."""
    desk.on_prices({t["tradingsymbol"]: t["last_price"] for t in ticks if "tradingsymbol" in t})
