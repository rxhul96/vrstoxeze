"""End-to-end engine tests on the paper broker with a fixed IST clock."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from optionsdesk.brokers.paper import PaperBroker
from optionsdesk.clock import IST, FixedClock
from optionsdesk.config import DeskConfig
from optionsdesk.engine import DeskEngine, DeskError
from optionsdesk.instruments import InstrumentRejected
from optionsdesk.models import (
    BacktestResult,
    DayStatus,
    Direction,
    ExitReason,
    SignalIn,
    StrategyRegistration,
    StrategyStats,
    Tier,
    TradeStatus,
)
from optionsdesk.store import DeskStore

SYM = "NIFTY24SEP25000CE"
PHRASE = "I ACCEPT THE RISK"
OPEN = datetime(2026, 9, 25, 10, 0, tzinfo=IST)


def make_config(**overrides) -> DeskConfig:
    return DeskConfig(_env_file=None, **overrides)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(OPEN)


@pytest.fixture
def engine(clock, tmp_path) -> DeskEngine:
    cfg = make_config(DESK_DB_PATH=str(tmp_path / "desk.sqlite3"))
    eng = DeskEngine(cfg, DeskStore(cfg.db_path), PaperBroker(), clock)
    eng.registry.register(
        StrategyRegistration(
            strategy_id="cvd",
            code_hash="h1",
            backtest=BacktestResult(oos_sharpe=1.8, win_rate=0.65, trades=100, max_drawdown_pct=5),
            tested_at=OPEN - timedelta(days=1),
        ),
        OPEN,
    )
    return eng


def sig(**kw) -> SignalIn:
    base = dict(
        strategy_id="cvd",
        code_hash="h1",
        tradingsymbol=SYM,
        direction=Direction.BUY,
        entry=100.0,
        stop_loss=90.0,
        target=120.0,
        confidence=0.8,
    )
    base.update(kw)
    return SignalIn(**base)


SURE = StrategyStats(live_win_rate=0.8, live_trades=40, oos_sharpe=2.0, confidence_percentile=0.95)


def test_unarmed_desk_trades_nothing(engine):
    rec = engine.submit_signal(sig())
    assert not rec.accepted and rec.reason_code == "NOT_ARMED"
    assert engine.store.list_trades() == []


def test_market_hours_guard(engine, clock):
    engine.arm()
    clock.set(datetime(2026, 9, 25, 15, 31, tzinfo=IST))
    assert engine.submit_signal(sig()).reason_code == "MARKET_CLOSED"
    clock.set(datetime(2026, 9, 26, 10, 0, tzinfo=IST))  # Saturday
    engine.arm()
    assert engine.submit_signal(sig()).reason_code == "MARKET_CLOSED"


def test_non_option_signals_are_rejected_in_code(engine):
    engine.arm()
    with pytest.raises(InstrumentRejected):
        engine.submit_signal(sig(tradingsymbol="NIFTY24SEPFUT"))
    with pytest.raises(InstrumentRejected):
        engine.submit_signal(sig(exchange="NSE", tradingsymbol="RELIANCE24SEP3000CE"))
    with pytest.raises(InstrumentRejected, match="writing"):
        engine.submit_signal(sig(direction=Direction.SELL, stop_loss=110, target=80))
    with pytest.raises(InstrumentRejected, match="stop_loss < entry < target"):
        engine.submit_signal(sig(stop_loss=105))
    assert engine.store.list_trades() == [] and engine.store.list_signals() == []


def test_paper_trade_lifecycle_target_hit(engine):
    engine.arm(actor="rahul")
    rec = engine.submit_signal(sig())
    assert rec.accepted and rec.tier == Tier.BASE and rec.trade_id
    trade = engine.store.get_trade(rec.trade_id)
    assert trade.status == TradeStatus.OPEN and trade.fill_price == 100.0
    assert trade.quantity == 75 and trade.lots == 1 and trade.mode == "paper"
    assert engine.state.trades_today == 1

    assert engine.on_prices({SYM: 110.0}) == []  # neither level hit
    closed = engine.on_prices({SYM: 121.0})
    assert len(closed) == 1
    t = closed[0]
    assert t.status == TradeStatus.CLOSED and t.exit_reason == ExitReason.TARGET
    assert t.realized_pnl == pytest.approx((121.0 - 100.0) * 75)
    st = engine.state
    assert (st.trades_today, st.losses_today, st.realized_pnl_today) == (1, 0, pytest.approx(1575.0))
    assert engine.positions() == []
    events = [e.event for e in engine.store.list_risk_events()]
    assert events[:2] == ["TRADE_CLOSED", "TRADE_OPENED"] and "ARMED" in events


def test_stop_loss_counts_as_loss_and_three_losses_stop_the_day(engine):
    engine.arm()
    for _ in range(3):
        engine.on_prices({SYM: 100.0})  # fresh tick at the entry level
        rec = engine.submit_signal(sig())
        assert rec.accepted
        engine.on_prices({SYM: 89.0})
    st = engine.state
    assert st.losses_today == 3 and st.day_status == DayStatus.STOPPED_LOSSES
    rec = engine.submit_signal(sig(stats=SURE))
    assert rec.reason_code == "STOPPED_LOSSES"
    with pytest.raises(DeskError, match="cannot arm"):
        engine.arm()
    engine.clear_stop(PHRASE, actor="rahul", note="reviewed tape")
    assert engine.state.day_status == DayStatus.ACTIVE
    assert engine.store.list_risk_events()[0].event == "STOP_CLEARED"
    # still blocked from opening trade 4 because losses_today == 3
    assert engine.submit_signal(sig(stats=SURE)).reason_code == "PNL_NOT_POSITIVE"


def test_fourth_trade_needs_sure_shot(engine):
    engine.arm()
    for _ in range(3):
        engine.submit_signal(sig())
        engine.on_prices({SYM: 121.0})
    assert engine.state.trades_today == 3 and engine.state.realized_pnl_today > 0
    weak = engine.submit_signal(sig())
    assert weak.reason_code == "NOT_SURE_SHOT"
    strong = engine.submit_signal(sig(stats=SURE))
    assert strong.accepted and strong.tier == Tier.SURE_SHOT
    engine.on_prices({SYM: 121.0})
    fifth = engine.submit_signal(sig(stats=SURE))
    assert fifth.accepted
    assert engine.state.day_status == DayStatus.STOPPED_CAP
    assert engine.submit_signal(sig(stats=SURE)).reason_code == "STOPPED_CAP"
    with pytest.raises(DeskError, match="cannot be cleared"):
        engine.clear_stop(PHRASE)


def test_confidence_percentile_is_derived_from_history(engine):
    engine.arm()
    # Seed 20 rejected signals (weak stats) with low confidence to build a history.
    for i in range(20):
        engine.submit_signal(sig(strategy_id="other", confidence=0.1 + i * 0.01))
    for _ in range(3):
        engine.submit_signal(sig())
        engine.on_prices({SYM: 121.0})
    stats = StrategyStats(live_win_rate=0.8, live_trades=40, oos_sharpe=2.0)  # no percentile supplied
    rec = engine.submit_signal(sig(confidence=0.99, stats=stats))
    assert rec.reason_code == "NOT_SURE_SHOT" and "percentile" in rec.reason  # cvd has only 3 samples
    for _ in range(20):
        engine.submit_signal(sig(strategy_id="other", confidence=0.5))
    rec = engine.submit_signal(sig(strategy_id="other", confidence=0.99, stats=stats))
    assert rec.reason_code == "STRATEGY_NOT_ELIGIBLE"  # 'other' is not registered, but percentile computed
    assert "not registered" in rec.reason


def test_ineligible_strategy_variants(engine):
    engine.arm()
    assert engine.submit_signal(sig(strategy_id="nope")).reason_code == "STRATEGY_NOT_ELIGIBLE"
    stale = engine.submit_signal(sig(code_hash="h2"))
    assert stale.reason_code == "STRATEGY_NOT_ELIGIBLE" and stale.eligibility.value == "STALE"
    engine.registry.register(
        StrategyRegistration(
            strategy_id="bad",
            code_hash="x",
            backtest=BacktestResult(oos_sharpe=0.2, win_rate=0.3, trades=5),
            tested_at=OPEN,
        ),
        OPEN,
    )
    failed = engine.submit_signal(sig(strategy_id="bad", code_hash="x"))
    assert failed.eligibility.value == "FAILED"


def test_kill_switch_flattens_and_closes(engine):
    engine.arm()
    engine.submit_signal(sig())
    engine.on_prices({SYM: 95.0})
    report = engine.kill(actor="rahul", reason="news shock")
    assert engine.state.day_status == DayStatus.STOPPED_MANUAL
    assert report["closed_trades"] and report["flatten_orders"][0]["tradingsymbol"] == SYM
    t = engine.store.list_trades()[0]
    assert t.status == TradeStatus.CLOSED and t.exit_reason == ExitReason.KILL_SWITCH
    assert t.realized_pnl == pytest.approx(-5.0 * 75)
    assert engine.state.losses_today == 1
    assert engine.positions() == []
    assert engine.submit_signal(sig()).reason_code == "STOPPED_MANUAL"
    ev = engine.store.list_risk_events()
    kill_ev = next(e for e in ev if e.event == "KILL_SWITCH")
    assert kill_ev.actor == "rahul" and kill_ev.reason == "news shock"


def test_state_persists_across_restart(engine, clock, tmp_path):
    engine.arm()
    engine.submit_signal(sig())
    engine.on_prices({SYM: 89.0})
    cfg = engine.config
    engine.store.close()
    reborn = DeskEngine(cfg, DeskStore(cfg.db_path), PaperBroker(), clock)
    st = reborn.state
    assert (st.trades_today, st.losses_today, st.armed_for_day) == (1, 1, OPEN.date())


def test_day_rolls_at_0915_and_requires_rearm(engine, clock):
    engine.arm()
    engine.submit_signal(sig())
    clock.set(datetime(2026, 9, 25, 15, 29, tzinfo=IST))
    engine.refresh()
    assert engine.state.trades_today == 1  # same session
    clock.set(datetime(2026, 9, 28, 9, 15, tzinfo=IST))  # Monday open
    status = engine.status()
    assert status["risk"]["trades_today"] == 0 and status["armed"] is False
    assert engine.submit_signal(sig()).reason_code == "NOT_ARMED"
    assert engine.store.list_risk_events()[0].event == "DAY_RESET"


def test_manual_close_and_lot_config(engine):
    engine.arm()
    rec = engine.submit_signal(sig(tradingsymbol="BANKNIFTY24SEP52000PE", entry=300, stop_loss=250, target=400, lots=2))
    t = engine.store.get_trade(rec.trade_id)
    assert t.quantity == 2 * engine.config.lot_size_banknifty
    closed = engine.close_trade(t.id, price=310.0)
    assert closed.exit_reason == ExitReason.MANUAL and closed.realized_pnl == pytest.approx(10 * t.quantity)
    with pytest.raises(DeskError):
        engine.close_trade(t.id)


def test_lots_above_max_are_rejected(engine):
    engine.arm()
    with pytest.raises(InstrumentRejected, match="DESK_MAX_LOTS"):
        engine.submit_signal(sig(lots=99))


def test_live_broker_requires_flag(tmp_path, clock):
    class LiveStub(PaperBroker):
        is_live = True
        name = "stub"

    cfg = make_config(DESK_DB_PATH=str(tmp_path / "x.sqlite3"))
    with pytest.raises(DeskError, match="ALLOW_LIVE_ORDERS"):
        DeskEngine(cfg, DeskStore(cfg.db_path), LiveStub(), clock)


def test_live_mode_requires_per_order_confirmation(tmp_path, clock):
    class LiveStub(PaperBroker):
        is_live = True
        name = "stub"

    cfg = make_config(DESK_DB_PATH=str(tmp_path / "x.sqlite3"), ALLOW_LIVE_ORDERS="true", DESK_LIVE_CONFIRM_TTL_SEC=60)
    eng = DeskEngine(cfg, DeskStore(cfg.db_path), LiveStub(), clock)
    assert eng.mode == "live"
    eng.registry.register(
        StrategyRegistration(
            strategy_id="cvd",
            code_hash="h1",
            backtest=BacktestResult(oos_sharpe=1.8, win_rate=0.65, trades=100),
            tested_at=OPEN,
        ),
        OPEN,
    )
    eng.arm()
    eng.broker.set_price(SYM, 100.0)
    rec = eng.submit_signal(sig())
    assert rec.accepted and rec.reason_code == "PENDING_LIVE_CONFIRMATION"
    trade = eng.store.get_trade(rec.trade_id)
    assert trade.status == TradeStatus.PENDING_CONFIRMATION
    assert eng.state.trades_today == 0  # nothing counted until it is actually placed
    assert eng.broker.positions() == []

    with pytest.raises(DeskError, match="phrase"):
        eng.confirm_live(trade.id, "nope")
    confirmed = eng.confirm_live(trade.id, PHRASE, actor="rahul")
    assert confirmed.status == TradeStatus.OPEN and eng.state.trades_today == 1
    assert eng.broker.positions()[0].quantity == 75

    # a second pending trade expires if not confirmed in time
    rec2 = eng.submit_signal(sig())
    clock.advance(seconds=61)
    eng.refresh()
    assert eng.store.get_trade(rec2.trade_id).status == TradeStatus.EXPIRED
    with pytest.raises(DeskError, match="not awaiting"):
        eng.confirm_live(rec2.trade_id, PHRASE)

    # a pending trade is cancelled by the kill switch and by the operator
    rec3 = eng.submit_signal(sig())
    assert eng.cancel_pending(rec3.trade_id).status == TradeStatus.CANCELLED
    rec4 = eng.submit_signal(sig())
    eng.kill()
    assert eng.store.get_trade(rec4.trade_id).status == TradeStatus.CANCELLED


def test_governor_reevaluated_at_live_confirmation(tmp_path, clock):
    class LiveStub(PaperBroker):
        is_live = True
        name = "stub"

    cfg = make_config(DESK_DB_PATH=str(tmp_path / "x.sqlite3"), ALLOW_LIVE_ORDERS="true")
    eng = DeskEngine(cfg, DeskStore(cfg.db_path), LiveStub(), clock)
    eng.registry.register(
        StrategyRegistration(
            strategy_id="cvd",
            code_hash="h1",
            backtest=BacktestResult(oos_sharpe=2, win_rate=0.7, trades=100),
            tested_at=OPEN,
        ),
        OPEN,
    )
    eng.arm()
    eng.broker.set_price(SYM, 100.0)
    pending = eng.submit_signal(sig())
    eng.disarm()
    with pytest.raises(DeskError, match="NOT_ARMED|not armed"):
        eng.confirm_live(pending.trade_id, PHRASE)
    assert eng.store.get_trade(pending.trade_id).status == TradeStatus.REJECTED
