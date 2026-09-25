"""Trading Desk integration: router mount, contract symbols, and the signal adapter mapping."""
from __future__ import annotations

import logging
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from backend.trading_desk import adapter as adapter_mod
from backend.trading_desk.adapter import SOURCES, AdapterSettings, SignalAdapter
from backend.trading_desk.contracts import atm_strike, next_expiry, option_symbol
from backend.trading_desk.runtime import DeskRuntime, _select_broker
from optionsdesk.brokers.paper import PaperBroker
from optionsdesk.clock import IST, FixedClock
from optionsdesk.config import DeskConfig
from optionsdesk.engine import DeskEngine
from optionsdesk.models import BacktestResult, Direction, StrategyRegistration, TradeStatus
from optionsdesk.store import DeskStore

NOW = datetime(2026, 9, 25, 10, 0, tzinfo=IST)  # Friday, NSE open
SPOT = 24850.0


# ----------------------------------------------------------------------------- fixtures


def make_engine(**cfg_overrides) -> DeskEngine:
    cfg = DeskConfig(_env_file=None, ALLOW_LIVE_ORDERS=False, DESK_MARKET_HOURS_ONLY=True, **cfg_overrides)
    return DeskEngine(cfg, DeskStore(":memory:"), PaperBroker(), clock=FixedClock(NOW))


def snap(**over) -> dict:
    """Neutral analyzer snapshot; override individual sources to flip a bias."""
    rows = [
        {"strike": 24800, "ce": {"ltp": 150.0}, "pe": {"ltp": 90.0}},
        {"strike": 24850, "atm": True, "ce": {"ltp": 120.0}, "pe": {"ltp": 115.0}},
        {"strike": 24900, "ce": {"ltp": 95.0}, "pe": {"ltp": 145.0}},
    ]
    base = {
        "spot": SPOT,
        "ts": NOW.isoformat(),
        "chain": {"atm": 24850, "step": 50, "rows": rows},
        "ta": {"atr": 40.0, "bias": "NEUTRAL"},
        "cvd": {"bias": "NEUTRAL", "event": None, "label": "flat"},
        "oi_flow": {"bias": "NEUTRAL", "confidence": 0.2},
        "ict": {"bias": "NEUTRAL", "events": []},
        "master": {"bias": "NEUTRAL", "headline": "NO HIGH-CONFIDENCE SIGNAL"},
        "score_detail": {"raw": 0},
        "signal": {"signal_id": None, "direction": "NO SIGNAL", "instrument_type": "NIFTY", "state": "WATCHING"},
    }
    base.update(over)
    return base


def composite(direction="BULLISH", signal_id="sig-1", conf=0.8) -> dict:
    up = direction == "BULLISH"
    return {
        "signal_id": signal_id,
        "direction": direction,
        "instrument_type": "NIFTY",
        "state": "TRIGGERED",
        "confidence": conf,
        "target_1": SPOT + 40 if up else SPOT - 40,
        "invalidation": SPOT - 44 if up else SPOT + 44,
        "reasons": ["cvd: BULLISH (+14.0)"],
    }


class CapturingSink:
    def __init__(self, engine: DeskEngine):
        self.engine = engine
        self.signals = []

    def __call__(self, sig):
        self.signals.append(sig)
        return self.engine.submit_signal(sig, actor="test")


def make_adapter(engine: DeskEngine, **settings):
    sink = CapturingSink(engine)
    ad = SignalAdapter(engine, AdapterSettings(**settings), sink=sink)
    ad.register_strategies()
    return ad, sink


def make_eligible(engine: DeskEngine, strategy_id: str, code_hash: str) -> None:
    engine.registry.register(
        StrategyRegistration(
            strategy_id=strategy_id,
            code_hash=code_hash,
            backtest=BacktestResult(oos_sharpe=1.8, win_rate=0.62, trades=120, max_drawdown_pct=8),
            tested_at=NOW,
        ),
        NOW,
    )


# ----------------------------------------------------------------------------- app mount


def test_desk_router_mounted_paper_by_default():
    from backend.main import app, hub
    c = TestClient(app)
    st = c.get("/desk/status")
    assert st.status_code == 200
    assert st.json()["mode"] == "paper"
    assert st.json()["broker"] == "paper"
    assert hub.desk.config.allow_live_orders is False
    desk = c.get("/api/desk").json()
    assert desk["mounted"] and desk["path"] == "/desk" and desk["mode"] == "paper"
    ids = {s["strategy_id"] for s in c.get("/desk/strategies").json()}
    assert {s.strategy_id for s in SOURCES} <= ids
    assert c.get("/api/status").json()["desk"]["mode"] == "paper"


def test_desk_ui_bundle_and_frontend_entry_served():
    from backend.main import app
    c = TestClient(app)
    assert c.get("/static/desk/optionsdesk-ui.js").status_code == 200
    assert c.get("/static/desk/optionsdesk-ui.css").status_code == 200
    js = c.get("/static/desk.js")
    assert js.status_code == 200
    assert b"KILL SWITCH" in js.content
    html = c.get("/").content
    assert b'data-win="desk"' in html and b"Trading Desk" in html
    assert b'id="desk-panel-host"' in html


def test_signal_endpoint_rejects_non_option():
    from backend.main import app
    c = TestClient(app)
    r = c.post(
        "/desk/signals",
        json={
            "strategy_id": "composite_score", "tradingsymbol": "NIFTY 50", "exchange": "NSE",
            "direction": "BUY", "entry": 100, "stop_loss": 90, "target": 120, "confidence": 0.8,
        },
    )
    assert r.status_code == 422


# ----------------------------------------------------------------------------- contracts


def test_next_expiry_tuesday_rules():
    always = lambda d: d.weekday() < 5  # noqa: E731
    # Friday -> next Tuesday, which is the last Tuesday of September => monthly contract.
    exp, monthly = next_expiry(NOW, 1, always)
    assert (exp, monthly) == (date(2026, 9, 29), True)
    # Mid-month Tuesday morning -> same-day weekly.
    exp, monthly = next_expiry(datetime(2026, 10, 6, 10, 0, tzinfo=IST), 1, always)
    assert (exp, monthly) == (date(2026, 10, 6), False)
    # After the close on expiry day -> roll a week.
    exp, _ = next_expiry(datetime(2026, 10, 6, 15, 45, tzinfo=IST), 1, always)
    assert exp == date(2026, 10, 13)
    # Holiday on the scheduled Tuesday -> previous trading day (Monday).
    exp, _ = next_expiry(datetime(2026, 10, 1, 10, 0, tzinfo=IST), 1, lambda d: d != date(2026, 10, 6) and d.weekday() < 5)
    assert exp == date(2026, 10, 5)


def test_option_symbol_formats_match_kite():
    assert option_symbol("NIFTY", date(2026, 9, 29), True, 24850, "CE") == "NIFTY26SEP24850CE"
    assert option_symbol("NIFTY", date(2026, 10, 6), False, 25000, "PE") == "NIFTY26O0625000PE"
    assert option_symbol("NIFTY", date(2026, 3, 3), False, 23500, "CE") == "NIFTY263" + "03" + "23500CE"
    assert atm_strike(24862.3) == 24850
    with pytest.raises(ValueError):
        option_symbol("NIFTY", date(2026, 9, 29), True, 24850, "FUT")


# ----------------------------------------------------------------------------- adapter


def test_adapter_registers_every_source_as_not_tested():
    engine = make_engine()
    ad, _ = make_adapter(engine)
    recs = {r.strategy_id: r for r in engine.registry.list(NOW)}
    for src in SOURCES:
        assert src.strategy_id in recs
        assert recs[src.strategy_id].status.value == "NOT_TESTED"
        assert recs[src.strategy_id].code_hash == ad.code_hashes[src.strategy_id]
    # Re-running never overwrites an operator's backtest.
    make_eligible(engine, "cvd_flow", ad.code_hashes["cvd_flow"])
    assert ad.register_strategies() == []
    assert engine.registry.get("cvd_flow", NOW).status.value == "ELIGIBLE"


@pytest.mark.parametrize(
    "strategy_id,override,kind",
    [
        ("composite_score", {"signal": composite("BULLISH")}, "CE"),
        ("composite_score", {"signal": composite("BEARISH")}, "PE"),
        ("cvd_flow", {"cvd": {"bias": "BULLISH", "event": "genuine_buying"}}, "CE"),
        ("oi_flow", {"oi_flow": {"bias": "BEARISH", "confidence": 0.7, "call": {"label": "writing"}, "put": {"label": "buying"}}}, "PE"),
        ("ict_liquidity", {"ict": {"bias": "BULLISH", "events": [{"type": "sweep"}, {"type": "fvg"}]}}, "CE"),
        ("price_action_ta", {"ta": {"atr": 40.0, "bias": "BEARISH", "event": "vwap_reject"}}, "PE"),
        ("ai_master_analyst", {"master": {"bias": "BULLISH", "headline": "MASTER BIAS: BULLISH"}, "score_detail": {"raw": 40}}, "CE"),
    ],
)
def test_each_source_maps_to_its_strategy_and_atm_option(strategy_id, override, kind):
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES=strategy_id)
    out = ad.on_snapshot(snap(**override))
    assert len(sink.signals) == 1
    sig = sink.signals[0]
    assert sig.strategy_id == strategy_id
    assert sig.code_hash == ad.code_hashes[strategy_id]
    assert sig.tradingsymbol == f"NIFTY26SEP24850{kind}"
    assert sig.exchange == "NFO" and sig.direction == Direction.BUY
    assert sig.stop_loss < sig.entry < sig.target
    assert sig.entry == (120.0 if kind == "CE" else 115.0)  # ATM premium from the chain
    # Governor order: NOT_ARMED comes before eligibility; either way nothing trades unarmed / untested.
    assert out[0]["outcome"] == "rejected" and out[0]["reason_code"] == "NOT_ARMED"
    assert engine.store.list_trades() == []


def test_composite_levels_are_delta_scaled_from_spot_targets():
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES="composite_score", DESK_ADAPTER_ATM_DELTA=0.5)
    ad.on_snapshot(snap(signal=composite("BULLISH")))
    sig = sink.signals[0]
    assert sig.entry == 120.0
    assert sig.target == 140.0  # +40 spot pts * 0.5
    assert sig.stop_loss == 98.0  # -44 spot pts * 0.5
    assert sig.meta["strike"] == 24850 and sig.meta["expiry"] == "2026-09-29" and sig.meta["monthly"] is True
    assert sig.meta["analyzer_signal_id"] == "sig-1"


def test_adapter_emits_once_per_bias_transition_and_rearms_on_neutral():
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES="cvd_flow", DESK_ADAPTER_COOLDOWN_SEC=0)
    bull = snap(cvd={"bias": "BULLISH"})
    ad.on_snapshot(bull)
    ad.on_snapshot(bull)
    ad.on_snapshot(bull)
    assert len(sink.signals) == 1
    ad.on_snapshot(snap(cvd={"bias": "BEARISH"}))  # flip counts as a new edge
    assert len(sink.signals) == 2 and sink.signals[-1].tradingsymbol.endswith("PE")
    ad.on_snapshot(snap())  # neutral re-arms
    ad.on_snapshot(snap(cvd={"bias": "BEARISH"}))
    assert len(sink.signals) == 3


def test_adapter_min_confidence_and_cooldown():
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES="oi_flow", DESK_ADAPTER_MIN_CONFIDENCE=0.6, DESK_ADAPTER_COOLDOWN_SEC=300)
    ad.on_snapshot(snap(oi_flow={"bias": "BULLISH", "confidence": 0.4}))
    assert sink.signals == []  # weak transition is not consumed...
    ad.on_snapshot(snap(oi_flow={"bias": "BULLISH", "confidence": 0.7}))
    assert len(sink.signals) == 1  # ...so it fires once confidence is there
    ad.on_snapshot(snap())
    ad.on_snapshot(snap(oi_flow={"bias": "BEARISH", "confidence": 0.7}))
    assert len(sink.signals) == 1  # cooldown holds the next edge
    engine.clock.advance(seconds=301)
    ad.on_snapshot(snap(oi_flow={"bias": "BEARISH", "confidence": 0.7}))
    assert len(sink.signals) == 2


def test_adapter_drops_non_option_instruments_with_log_line(caplog):
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES="composite_score")
    bad = composite("BULLISH")
    bad["instrument_type"] = "NIFTY FUT"
    with caplog.at_level(logging.WARNING, logger="nifty.desk.adapter"):
        out = ad.on_snapshot(snap(signal=bad))
    assert sink.signals == []
    assert out and out[0]["outcome"] == "dropped"
    assert ad.counters["dropped"] == 1
    assert any("DROPPED non-NSE-option" in r.getMessage() for r in caplog.records)
    # Nothing was stored in the desk either.
    assert engine.store.list_signals() == []


def test_adapter_drops_snapshot_without_spot(caplog):
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES="cvd_flow")
    with caplog.at_level(logging.WARNING, logger="nifty.desk.adapter"):
        ad.on_snapshot(snap(spot=0, cvd={"bias": "BULLISH"}))
    assert sink.signals == [] and ad.counters["dropped"] == 1


def test_eligible_strategy_opens_paper_trade_and_exits_on_chain_prices():
    engine = make_engine()
    ad, sink = make_adapter(engine, DESK_ADAPTER_SOURCES="composite_score")
    make_eligible(engine, "composite_score", ad.code_hashes["composite_score"])
    engine.arm(actor="test")
    out = ad.on_snapshot(snap(signal=composite("BULLISH")))
    assert out[0]["outcome"] == "accepted" and out[0]["tier"] == "BASE"
    trades = engine.store.list_trades([TradeStatus.OPEN])
    assert len(trades) == 1 and trades[0].tradingsymbol == "NIFTY26SEP24850CE"
    assert trades[0].fill_price == 120.0 and trades[0].mode == "paper"
    assert engine.state.trades_today == 1

    # Next bar: the analyzer chain marks the ATM CE above target -> desk closes the trade.
    hot = snap(signal=composite("BULLISH"))
    hot["chain"]["rows"][1]["ce"]["ltp"] = 141.0
    ad.on_snapshot(hot)
    closed = engine.store.list_trades([TradeStatus.CLOSED])
    assert len(closed) == 1 and closed[0].exit_reason.value == "TARGET"
    assert closed[0].realized_pnl > 0
    assert len(sink.signals) == 1  # same bias, no re-entry


def test_adapter_source_stays_signal_only():
    import inspect
    src = inspect.getsource(adapter_mod)
    for name in ("place_order", "cancel_order", "modify_order", "KiteBroker", "kiteconnect"):
        assert name not in src


def test_adapter_summary_lists_sources_and_counters():
    engine = make_engine()
    ad, _ = make_adapter(engine)
    s = ad.summary()
    assert {x["strategy_id"] for x in s["sources"]} == {x.strategy_id for x in SOURCES}
    assert s["counters"]["emitted"] == 0 and s["underlying"] == "NIFTY"


# ----------------------------------------------------------------------------- runtime / kite


def test_live_broker_requires_explicit_flag(monkeypatch):
    cfg = DeskConfig(_env_file=None, ALLOW_LIVE_ORDERS=False, KITE_API_KEY="k", KITE_ACCESS_TOKEN="t")
    broker, fallback = _select_broker(cfg)
    assert broker.name == "paper" and fallback is None
    cfg = DeskConfig(_env_file=None, ALLOW_LIVE_ORDERS=True)  # no api key
    broker, fallback = _select_broker(cfg)
    assert broker.name == "paper" and "PAPER" in fallback


def test_kite_token_is_shared_with_live_desk_broker():
    class FakeKite:
        def __init__(self):
            self.token = None

        def set_access_token(self, t):
            self.token = t

    class FakeLiveBroker(PaperBroker):
        name = "kite"
        is_live = True

        def __init__(self):
            super().__init__()
            self.kite = FakeKite()

    from backend.config import get_settings
    cfg = DeskConfig(_env_file=None, ALLOW_LIVE_ORDERS=True, KITE_API_KEY="k", KITE_ACCESS_TOKEN="old")
    engine = DeskEngine(cfg, DeskStore(":memory:"), FakeLiveBroker(), clock=FixedClock(NOW))
    rt = DeskRuntime(get_settings(), cfg, engine, SignalAdapter(engine, AdapterSettings(), sink=lambda s: None))
    assert engine.mode == "live"
    rt.attach_kite_token("fresh-token")
    assert engine.broker.kite.token == "fresh-token"
    assert rt.summary()["kite_session"] == "shared"


def test_paper_runtime_accepts_token_without_broker_switch():
    from backend.main import hub
    hub.desk.attach_kite_token("tok")
    assert hub.desk.engine.mode == "paper" and hub.desk.engine.broker.name == "paper"
    assert hub.desk.summary()["kite_session"] == "shared"
