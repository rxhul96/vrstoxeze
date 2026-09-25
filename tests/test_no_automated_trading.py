"""Prove the analyzer cannot trade on its own.

Order placement exists in exactly one place: the vendored governed desk (``desk/src/optionsdesk``),
mounted separately under ``/desk``. Everything else in this repo is signal-only.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "venv", "node_modules", ".git", "data", "tests"}
# The only directory allowed to contain broker execution calls.
DESK_PACKAGE = ROOT / "desk" / "src" / "optionsdesk"
ORDER_CALLS = {
    "place_order", "modify_order", "cancel_order",
    "execute_order", "exit_order", "square_off",
}


def source_files(include_desk: bool = False):
    for p in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not include_desk and DESK_PACKAGE in p.parents:
            continue
        yield p


def order_call_sites(paths):
    hits = []
    for p in paths:
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name in ORDER_CALLS:
                    hits.append((p, node.lineno, name))
    return hits


def test_execution_flag_is_false():
    from backend.safety.trading_disabled import TRADING_EXECUTION_ENABLED
    assert TRADING_EXECUTION_ENABLED is False


def test_no_place_order_calls_in_analyzer_source():
    hits = order_call_sites(source_files(include_desk=False))
    assert [f"{p}:{line}:{name}" for p, line, name in hits] == []


def test_order_calls_exist_only_inside_desk_package():
    hits = order_call_sites(source_files(include_desk=True))
    assert hits, "the desk package is expected to contain the broker adapter"
    outside = [f"{p}:{line}:{name}" for p, line, name in hits if DESK_PACKAGE not in p.parents]
    assert outside == []
    modules = {p.relative_to(DESK_PACKAGE).as_posix() for p, _, _ in hits}
    assert modules <= {"brokers/base.py", "brokers/kite.py", "engine.py"}


def test_backend_only_reaches_desk_brokers_through_runtime():
    """The adapter submits signals; only the desk runtime may construct a broker."""
    offenders = []
    for p in (ROOT / "backend").rglob("*.py"):
        if "optionsdesk.brokers" in p.read_text(encoding="utf-8") and p.name != "runtime.py":
            offenders.append(str(p))
    assert offenders == []


def test_kite_wrapper_has_no_order_methods():
    from backend.kite.readonly import ReadOnlyKite
    from backend.safety.trading_disabled import TradingDisabledError
    k = ReadOnlyKite()
    for name in ("place_order", "modify_order", "cancel_order", "execute_order"):
        with pytest.raises((TradingDisabledError, AttributeError)):
            getattr(k, name)


def test_seal_blocks_fake_kite():
    from backend.safety.trading_disabled import TradingDisabledError, seal_kite_read_only

    class Fake:
        def place_order(self, *a, **k):
            return {"order_id": "should-never-run"}

        def quote(self):
            return {}

    sealed = seal_kite_read_only(Fake())
    with pytest.raises(TradingDisabledError):
        sealed.place_order()


def test_agents_have_no_broker_tools():
    from backend.agents.desk import FORBIDDEN_TOOLS, master_analyst, run_desk
    desk = run_desk({"price_action": {"bias": "BULLISH"}})
    master = master_analyst({}, {"bias": "NEUTRAL", "mixed": True, "raw": 0}, desk)
    assert master["tools"] == []
    assert master["execution"] is False
    for t in FORBIDDEN_TOOLS:
        blob = str(master) + str(desk)
        assert "place_order" not in blob


def test_http_has_no_usable_order_endpoint():
    from backend.main import app
    c = TestClient(app)
    for path in ("/api/exec/order", "/api/orders", "/api/order", "/api/exec/basket"):
        r = c.post(path, json={"tradingsymbol": "NIFTY", "qty": 1})
        assert r.status_code in (404, 405, 422)
        if r.headers.get("content-type", "").startswith("application/json"):
            body = r.json()
            assert body.get("would_place_order") is not True
            assert "order_id" not in body


def test_safety_endpoint():
    from backend.main import app
    r = TestClient(app).get("/api/safety")
    assert r.status_code == 200
    body = r.json()
    assert body["execution_enabled"] is False
    assert body["automated_trading"] is False
    assert body["kite_connections"] <= 1
    # The desk is declared, separate, and paper by default.
    assert body["trading_desk"]["path"] == "/desk"
    assert body["trading_desk"]["mode"] == "paper"
    assert body["trading_desk"]["allow_live_orders"] is False


def test_analyzer_kite_client_stays_sealed_with_desk_mounted():
    """Mounting the desk must not unseal the analyzer's own Kite wrapper."""
    from backend.main import hub
    from backend.safety.trading_disabled import TradingDisabledError
    with pytest.raises((TradingDisabledError, AttributeError)):
        hub.kite.kite.place_order  # noqa: B018 - attribute access is the assertion
    assert hub.desk.engine.broker.name == "paper"
