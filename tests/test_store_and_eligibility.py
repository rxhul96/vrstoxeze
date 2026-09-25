from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from optionsdesk.eligibility import EligibilityThresholds, StrategyRegistry, classify
from optionsdesk.models import BacktestResult, DayStatus, EligibilityStatus, RiskEvent, StrategyRegistration
from optionsdesk.risk_governor import RiskState
from optionsdesk.store import DeskStore
from tests.conftest import NOW, TODAY


def _event(**kw) -> RiskEvent:
    base = dict(
        trading_day=TODAY,
        event="TEST",
        from_status=DayStatus.ACTIVE,
        to_status=DayStatus.ACTIVE,
        trades_today=0,
        losses_today=0,
        realized_pnl_today=0.0,
    )
    base.update(kw)
    return RiskEvent(**base)


def test_state_survives_reopen(tmp_path):
    path = tmp_path / "desk.sqlite3"
    store = DeskStore(path)
    state = RiskState(
        trading_day=TODAY,
        armed_for_day=TODAY,
        trades_today=4,
        losses_today=2,
        realized_pnl_today=-120.5,
        day_status=DayStatus.ACTIVE,
    )
    store.save_state(state, [_event(event="TRADE_OPENED", trades_today=4)], NOW)
    store.close()

    reopened = DeskStore(path)
    assert reopened.load_latest_state() == state
    events = reopened.list_risk_events()
    assert len(events) == 1 and events[0].event == "TRADE_OPENED" and events[0].id == 1
    assert events[0].created_at == NOW


def test_risk_events_are_append_only():
    store = DeskStore(":memory:")
    store.save_state(RiskState(trading_day=TODAY), [_event(event="ARMED")], NOW)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("UPDATE risk_events SET event='HACKED' WHERE id=1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._conn.execute("DELETE FROM risk_events")
    assert store.list_risk_events()[0].event == "ARMED"


def test_save_state_assigns_event_ids_in_order():
    store = DeskStore(":memory:")
    saved = store.save_state(RiskState(trading_day=TODAY), [_event(event="A"), _event(event="B")], NOW)
    assert [e.id for e in saved] == [1, 2]
    assert [e.event for e in store.list_risk_events()] == ["B", "A"]  # newest first


# ------------------------------------------------------------------------------------------
# eligibility
# ------------------------------------------------------------------------------------------

TH = EligibilityThresholds(
    min_backtest_trades=30, min_oos_sharpe=1.0, min_win_rate=0.5, max_drawdown_pct=20, max_test_age_days=30
)


def _reg(**kw) -> StrategyRegistration:
    base = dict(
        strategy_id="cvd_breakout",
        code_hash="abc123",
        backtest=BacktestResult(oos_sharpe=1.8, win_rate=0.62, trades=120, max_drawdown_pct=8),
        tested_at=NOW - timedelta(days=2),
    )
    base.update(kw)
    return StrategyRegistration(**base)


def test_classify_not_tested():
    assert classify(None, TH, now=NOW)[0] == EligibilityStatus.NOT_TESTED
    assert classify(_reg(backtest=None), TH, now=NOW)[0] == EligibilityStatus.NOT_TESTED


def test_classify_stale_by_code_hash_and_age():
    status, why = classify(_reg(), TH, now=NOW, signal_code_hash="deadbeef")
    assert status == EligibilityStatus.STALE and "code_hash" in why
    status, why = classify(_reg(tested_at=NOW - timedelta(days=31)), TH, now=NOW)
    assert status == EligibilityStatus.STALE and "days old" in why


def test_classify_failed_lists_every_breach():
    reg = _reg(backtest=BacktestResult(oos_sharpe=0.4, win_rate=0.3, trades=10, max_drawdown_pct=35))
    status, why = classify(reg, TH, now=NOW)
    assert status == EligibilityStatus.FAILED
    for frag in ("trades 10", "Sharpe 0.4", "win rate 30%", "drawdown 35"):
        assert frag in why


def test_classify_eligible():
    assert classify(_reg(), TH, now=NOW, signal_code_hash="abc123")[0] == EligibilityStatus.ELIGIBLE


def test_registry_roundtrip():
    store = DeskStore(":memory:")
    reg = StrategyRegistry(store, TH)
    rec = reg.register(_reg(), NOW)
    assert rec.status == EligibilityStatus.ELIGIBLE
    assert reg.status_for_signal("cvd_breakout", "abc123", NOW)[0] == EligibilityStatus.ELIGIBLE
    assert reg.status_for_signal("cvd_breakout", "other", NOW)[0] == EligibilityStatus.STALE
    assert reg.status_for_signal("unknown", None, NOW)[0] == EligibilityStatus.NOT_TESTED
    # signals without a code_hash are accepted against the registered hash
    assert reg.status_for_signal("cvd_breakout", None, NOW)[0] == EligibilityStatus.ELIGIBLE
    assert [s.strategy_id for s in reg.list(NOW)] == ["cvd_breakout"]
