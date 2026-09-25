from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from optionsdesk.api import build_desk_router
from optionsdesk.app import create_app
from optionsdesk.brokers.paper import PaperBroker
from optionsdesk.clock import IST, FixedClock
from optionsdesk.config import DeskConfig
from optionsdesk.engine import DeskEngine
from optionsdesk.store import DeskStore

SYM = "NIFTY24SEP25000CE"
OPEN = datetime(2026, 9, 25, 10, 0, tzinfo=IST)
PHRASE = "I ACCEPT THE RISK"


@pytest.fixture
def client(tmp_path):
    cfg = DeskConfig(_env_file=None, DESK_DB_PATH=str(tmp_path / "d.sqlite3"))
    eng = DeskEngine(cfg, DeskStore(cfg.db_path), PaperBroker(), FixedClock(OPEN))
    app = create_app(eng)
    with TestClient(app) as c:
        c.post(
            "/desk/strategies",
            json={
                "strategy_id": "cvd",
                "code_hash": "h1",
                "backtest": {"oos_sharpe": 1.9, "win_rate": 0.66, "trades": 80, "max_drawdown_pct": 6},
                "tested_at": (OPEN - timedelta(days=1)).isoformat(),
            },
        ).raise_for_status()
        yield c


def signal(**kw):
    base = {
        "strategy_id": "cvd",
        "code_hash": "h1",
        "tradingsymbol": SYM,
        "exchange": "NFO",
        "direction": "BUY",
        "entry": 100,
        "stop_loss": 90,
        "target": 120,
        "confidence": 0.8,
    }
    base.update(kw)
    return base


def test_healthz_and_status(client):
    assert client.get("/healthz").json()["mode"] == "paper"
    s = client.get("/desk/status").json()
    assert s["risk"]["day_status"] == "ACTIVE" and s["armed"] is False
    assert s["config"]["allow_live_orders"] is False


def test_signal_flow_via_http(client):
    r = client.post("/desk/signals", json=signal())
    assert r.status_code == 200 and r.json()["reason_code"] == "NOT_ARMED"

    assert client.post("/desk/arm", json={"confirm": False}).status_code == 400
    r = client.post("/desk/arm", json={"confirm": True, "actor": "rahul"})
    assert r.status_code == 200 and r.json()["armed_for_day"] == "2026-09-25"

    r = client.post("/desk/signals", json=signal())
    body = r.json()
    assert body["accepted"] and body["tier"] == "BASE"
    trade_id = body["trade_id"]
    trades = client.get("/desk/trades", params={"status": "OPEN"}).json()
    assert [t["id"] for t in trades] == [trade_id]

    r = client.post("/desk/prices", json={"prices": {SYM: 121}})
    assert r.json()["closed"][0]["exit_reason"] == "TARGET"
    assert client.get("/desk/status").json()["risk"]["realized_pnl_today"] == pytest.approx(1575.0)
    events = client.get("/desk/risk-events").json()
    assert events[0]["event"] == "TRADE_CLOSED"
    assert client.get("/desk/strategies").json()[0]["status"] == "ELIGIBLE"
    assert client.get("/desk/signals").json()[0]["accepted"] is True


def test_non_option_rejected_with_422(client):
    client.post("/desk/arm", json={"confirm": True})
    r = client.post("/desk/signals", json=signal(tradingsymbol="NIFTY24SEPFUT"))
    assert r.status_code == 422 and "not an NSE option" in r.json()["detail"]
    r = client.post("/desk/signals", json=signal(exchange="BFO"))
    assert r.status_code == 422
    r = client.post("/desk/signals", json=signal(direction="SELL", stop_loss=110, target=80))
    assert r.status_code == 422 and "writing" in r.json()["detail"]
    assert client.get("/desk/trades").json() == []


def test_kill_and_clear_via_http(client):
    client.post("/desk/arm", json={"confirm": True})
    client.post("/desk/signals", json=signal())
    r = client.post("/desk/kill", json={"actor": "rahul", "reason": "manual"})
    assert r.status_code == 200 and r.json()["risk"]["day_status"] == "STOPPED_MANUAL"
    assert r.json()["closed_trades"]
    assert client.get("/desk/positions").json() == []
    r = client.post("/desk/clear-stop", json={"phrase": "wrong"})
    assert r.status_code == 409
    r = client.post("/desk/clear-stop", json={"phrase": PHRASE, "actor": "rahul", "note": "ok"})
    assert r.status_code == 200 and r.json()["day_status"] == "ACTIVE"
    assert client.get("/desk/trades/999").status_code == 404
    assert client.post("/desk/trades/1/close", json={}).status_code == 409  # already closed


def test_api_token_guard(tmp_path):
    cfg = DeskConfig(_env_file=None, DESK_DB_PATH=str(tmp_path / "d.sqlite3"), DESK_API_TOKEN="s3cret")
    eng = DeskEngine(cfg, DeskStore(cfg.db_path), PaperBroker(), FixedClock(OPEN))
    host = FastAPI()
    host.include_router(build_desk_router(eng, prefix="/api/desk"))
    c = TestClient(host)
    assert c.get("/api/desk/status").status_code == 401
    assert c.get("/api/desk/status", headers={"X-Desk-Token": "s3cret"}).status_code == 200
