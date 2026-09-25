"""Unit tests for the six governor rules plus their interactions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from optionsdesk.clock import IST
from optionsdesk.models import DayStatus, Tier
from optionsdesk.risk_governor import (
    ClearRejected,
    RiskState,
    SignalQuality,
    arm,
    clear_stop,
    disarm,
    evaluate_signal,
    fresh_state,
    is_sure_shot,
    kill_switch,
    record_trade_closed,
    record_trade_opened,
    roll_day,
)
from tests.conftest import NOW, TODAY

PHRASE = "I ACCEPT THE RISK"


def _open_n(state, limits, n):
    for _ in range(n):
        state = record_trade_opened(state, limits).state
    return state


# ------------------------------------------------------------------------------------------
# Rule 1: trade cap
# ------------------------------------------------------------------------------------------


def test_rule1_fifth_trade_flips_to_stopped_cap(armed, limits):
    state = _open_n(armed, limits, 4)
    assert state.day_status == DayStatus.ACTIVE
    t = record_trade_opened(state, limits)
    assert t.state.trades_today == 5
    assert t.state.day_status == DayStatus.STOPPED_CAP
    assert [e.event for e in t.events] == ["TRADE_OPENED", "STOPPED_CAP"]


def test_rule1_blocks_when_cap_reached(armed, limits, sure):
    state = replace(_open_n(armed, limits, 5), realized_pnl_today=5000.0)
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed
    assert d.reason_code == "STOPPED_CAP"


def test_rule1_defensive_path_when_status_stale(armed, limits, sure):
    # State says ACTIVE but counter is at the cap (e.g. hand-edited DB) -> block and flip.
    state = replace(armed, trades_today=5, realized_pnl_today=1.0)
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed
    assert d.reason_code == "TRADE_CAP"
    assert d.state.day_status == DayStatus.STOPPED_CAP
    assert d.events[0].event == "STOPPED_CAP"


def test_rule1_cap_is_never_clearable(armed, limits):
    state = _open_n(armed, limits, 5)
    with pytest.raises(ClearRejected, match="cannot be cleared"):
        clear_stop(state, phrase=PHRASE, expected_phrase=PHRASE)


# ------------------------------------------------------------------------------------------
# Rule 2: loss stop
# ------------------------------------------------------------------------------------------


def test_rule2_third_loss_flips_to_stopped_losses(armed, limits):
    state = _open_n(armed, limits, 3)
    state = record_trade_closed(state, limits, -100).state
    state = record_trade_closed(state, limits, -100).state
    assert state.day_status == DayStatus.ACTIVE
    t = record_trade_closed(state, limits, -100)
    assert t.state.losses_today == 3
    assert t.state.day_status == DayStatus.STOPPED_LOSSES
    assert [e.event for e in t.events] == ["TRADE_CLOSED", "STOPPED_LOSSES"]


def test_rule2_flat_or_winning_trade_is_not_a_loss(armed, limits):
    state = _open_n(armed, limits, 2)
    state = record_trade_closed(state, limits, 0.0).state
    state = record_trade_closed(state, limits, 250.0).state
    assert state.losses_today == 0
    assert state.realized_pnl_today == 250.0


def test_rule2_blocks_signals_and_does_not_auto_resume(armed, limits, sure):
    state = _open_n(armed, limits, 3)
    for _ in range(3):
        state = record_trade_closed(state, limits, -10).state
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed and d.reason_code == "STOPPED_LOSSES"
    # A later winning close does not resume the day.
    state = record_trade_closed(state, limits, +1000).state
    assert state.day_status == DayStatus.STOPPED_LOSSES


def test_rule2_manual_clear_requires_exact_phrase_and_is_logged(armed, limits):
    state = _open_n(armed, limits, 3)
    for _ in range(3):
        state = record_trade_closed(state, limits, -10).state
    with pytest.raises(ClearRejected, match="phrase"):
        clear_stop(state, phrase="i accept the risk", expected_phrase=PHRASE)
    t = clear_stop(state, phrase=PHRASE, expected_phrase=PHRASE, actor="rahul", note="reviewed")
    assert t.state.day_status == DayStatus.ACTIVE
    assert t.state.loss_stop_cleared is True
    ev = t.events[0]
    assert ev.event == "STOP_CLEARED"
    assert ev.actor == "rahul"
    assert ev.from_status == DayStatus.STOPPED_LOSSES and ev.to_status == DayStatus.ACTIVE
    assert "reviewed" in ev.reason


def test_rule2_after_clear_sure_shot_tier_still_requires_losses_below_limit(armed, limits, sure):
    state = _open_n(armed, limits, 3)
    for pnl in (-10, -10, -10):
        state = record_trade_closed(state, limits, pnl).state
    state = clear_stop(state, phrase=PHRASE, expected_phrase=PHRASE).state
    state = replace(state, realized_pnl_today=500.0)  # even with positive pnl...
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed
    assert d.reason_code == "LOSSES_AT_LIMIT"


# ------------------------------------------------------------------------------------------
# Rule 3: base tier (trades 1-3) needs arm + eligibility
# ------------------------------------------------------------------------------------------


def test_rule3_unarmed_day_trades_nothing(limits, weak):
    state = fresh_state(TODAY)
    d = evaluate_signal(state, limits, weak, strategy_eligible=True, now=NOW)
    assert not d.allowed and d.reason_code == "NOT_ARMED"


def test_rule3_arm_is_per_calendar_day(limits, weak):
    yesterday = TODAY - timedelta(days=1)
    state = RiskState(trading_day=TODAY, armed_for_day=yesterday)
    d = evaluate_signal(state, limits, weak, strategy_eligible=True, now=NOW)
    assert d.reason_code == "NOT_ARMED"
    t = arm(state, TODAY, actor="rahul")
    assert t.events[0].event == "ARMED"
    d = evaluate_signal(t.state, limits, weak, strategy_eligible=True, now=NOW)
    assert d.allowed and d.tier == Tier.BASE


def test_rule3_first_three_trades_allowed_with_weak_stats(armed, limits, weak):
    state = armed
    for n in range(3):
        d = evaluate_signal(state, limits, weak, strategy_eligible=True, now=NOW)
        assert d.allowed, d.reason
        assert d.tier == Tier.BASE
        assert f"trade {n + 1} of 3" in d.reason
        state = record_trade_opened(state, limits).state


def test_rule3_ineligible_strategy_is_blocked(armed, limits, sure):
    d = evaluate_signal(armed, limits, sure, strategy_eligible=False, now=NOW)
    assert not d.allowed and d.reason_code == "STRATEGY_NOT_ELIGIBLE"


def test_disarm_blocks_further_entries(armed, limits, weak):
    t = disarm(armed)
    assert t.events[0].event == "DISARMED"
    d = evaluate_signal(t.state, limits, weak, strategy_eligible=True, now=NOW)
    assert d.reason_code == "NOT_ARMED"


# ------------------------------------------------------------------------------------------
# Rule 4: trades 4-5 need pnl>0, losses<3 and sure-shot
# ------------------------------------------------------------------------------------------


def test_rule4_fourth_trade_blocked_without_positive_pnl(armed, limits, sure):
    state = _open_n(armed, limits, 3)
    state = replace(state, realized_pnl_today=0.0)
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed and d.reason_code == "PNL_NOT_POSITIVE"


def test_rule4_fourth_trade_blocked_when_not_sure_shot(armed, limits, weak):
    state = replace(_open_n(armed, limits, 3), realized_pnl_today=800.0)
    d = evaluate_signal(state, limits, weak, strategy_eligible=True, now=NOW)
    assert not d.allowed and d.reason_code == "NOT_SURE_SHOT"


def test_rule4_fourth_and_fifth_trades_allowed_as_sure_shot(armed, limits, sure):
    state = replace(_open_n(armed, limits, 3), realized_pnl_today=800.0)
    d4 = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert d4.allowed and d4.tier == Tier.SURE_SHOT
    state = record_trade_opened(state, limits).state
    d5 = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert d5.allowed and d5.tier == Tier.SURE_SHOT
    state = record_trade_opened(state, limits).state
    assert state.day_status == DayStatus.STOPPED_CAP


@pytest.mark.parametrize(
    "field,value,fragment",
    [
        ("live_trades", 19, "sample"),
        ("live_win_rate", 0.69, "win rate"),
        ("oos_sharpe", 1.49, "Sharpe"),
        ("confidence_percentile", 0.89, "percentile"),
        ("live_trades", None, "sample"),
        ("oos_sharpe", None, "Sharpe"),
    ],
)
def test_rule4_each_sure_shot_threshold_is_enforced(limits, sure, field, value, fragment):
    q = replace(sure, **{field: value})
    ok, why = is_sure_shot(q, limits.sure_shot)
    assert not ok
    assert fragment in why


def test_rule4_thresholds_are_configurable(armed, weak):
    from optionsdesk.risk_governor import RiskLimits, SureShotThresholds

    relaxed = RiskLimits(
        sure_shot=SureShotThresholds(
            min_win_rate=0.5, min_sample_trades=10, min_oos_sharpe=0.5, min_confidence_percentile=0.4
        )
    )
    state = replace(_open_n(armed, relaxed, 3), realized_pnl_today=1.0)
    d = evaluate_signal(state, relaxed, weak, strategy_eligible=True, now=NOW)
    assert d.allowed and d.tier == Tier.SURE_SHOT


# ------------------------------------------------------------------------------------------
# Rule 5: kill switch
# ------------------------------------------------------------------------------------------


def test_rule5_kill_switch_stops_day_and_blocks(armed, limits, sure):
    t = kill_switch(armed, actor="rahul")
    assert t.state.day_status == DayStatus.STOPPED_MANUAL
    assert t.events[0].event == "KILL_SWITCH" and t.events[0].actor == "rahul"
    d = evaluate_signal(t.state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed and d.reason_code == "STOPPED_MANUAL"


def test_rule5_kill_switch_never_weakens_a_stricter_stop(armed, limits):
    state = _open_n(armed, limits, 5)
    t = kill_switch(state)
    assert t.state.day_status == DayStatus.STOPPED_CAP
    assert t.events[0].event == "KILL_SWITCH"  # still logged


def test_rule5_manual_stop_can_be_cleared_with_phrase(armed, limits, weak):
    state = kill_switch(armed).state
    t = clear_stop(state, phrase=PHRASE, expected_phrase=PHRASE)
    assert t.state.day_status == DayStatus.ACTIVE
    assert t.state.loss_stop_cleared is False  # only a loss clear sets this
    d = evaluate_signal(t.state, limits, weak, strategy_eligible=True, now=NOW)
    assert d.allowed


# ------------------------------------------------------------------------------------------
# Rule 6: every transition is an audit event
# ------------------------------------------------------------------------------------------


def test_rule6_every_transition_emits_event_with_full_counters(armed, limits):
    t1 = record_trade_opened(armed, limits, trade_id=7, signal_id=3)
    (e1,) = t1.events
    assert (e1.event, e1.trade_id, e1.signal_id, e1.trades_today) == ("TRADE_OPENED", 7, 3, 1)
    assert e1.from_status == e1.to_status == DayStatus.ACTIVE

    t2 = record_trade_closed(t1.state, limits, -42.5, trade_id=7)
    (e2,) = t2.events
    assert e2.event == "TRADE_CLOSED"
    assert e2.details == {"realized_pnl": -42.5, "is_loss": True}
    assert e2.losses_today == 1 and e2.realized_pnl_today == -42.5


def test_rule6_noop_calls_emit_nothing(armed):
    assert arm(armed, TODAY).events == ()
    assert disarm(fresh_state(TODAY)).events == ()
    assert roll_day(armed, NOW).events == ()


# ------------------------------------------------------------------------------------------
# Day reset at 09:15 IST
# ------------------------------------------------------------------------------------------


def test_day_resets_at_0915_ist(armed, limits):
    state = _open_n(armed, limits, 5)
    before_open = datetime(2026, 9, 28, 9, 14, tzinfo=IST)  # Monday, pre-open
    assert roll_day(state, before_open).state.trading_day == TODAY.replace(day=27)  # still Sunday's session
    # ... which is a different day from Friday, so counters reset then anyway.
    at_open = datetime(2026, 9, 28, 9, 15, tzinfo=IST)
    t = roll_day(state, at_open)
    assert t.state == fresh_state(at_open.date())
    assert t.state.armed_for_day is None  # must re-arm each day
    assert t.events[0].event == "DAY_RESET"
    assert t.events[0].from_status == DayStatus.STOPPED_CAP
    assert t.events[0].details["previous"]["trades_today"] == 5


def test_same_day_does_not_reset(armed, limits):
    state = _open_n(armed, limits, 2)
    later = NOW + timedelta(hours=5)
    assert roll_day(state, later).state == state


def test_signal_on_unrolled_state_is_refused(armed, limits, sure):
    tomorrow = NOW + timedelta(days=1)
    d = evaluate_signal(armed, limits, sure, strategy_eligible=True, now=tomorrow)
    assert not d.allowed and d.reason_code == "DAY_NOT_ROLLED"


# ------------------------------------------------------------------------------------------
# Interaction tests
# ------------------------------------------------------------------------------------------


def test_interaction_third_loss_beats_queued_sure_shot_fourth(armed, limits, sure):
    """3 trades open, 2 already lost, pnl positive; a sure-shot 4th is queued, then the 3rd loss lands."""
    state = _open_n(armed, limits, 3)
    state = record_trade_closed(state, limits, -100).state
    state = record_trade_closed(state, limits, -100).state
    state = replace(state, realized_pnl_today=+300.0)  # earlier win keeps pnl positive
    queued = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert queued.allowed and queued.tier == Tier.SURE_SHOT

    # The third open trade closes at a loss before the queued signal executes.
    state = record_trade_closed(state, limits, -50).state
    assert state.day_status == DayStatus.STOPPED_LOSSES
    again = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not again.allowed and again.reason_code == "STOPPED_LOSSES"


def test_interaction_cap_wins_over_later_loss_stop(armed, limits):
    state = _open_n(armed, limits, 5)
    assert state.day_status == DayStatus.STOPPED_CAP
    for _ in range(3):
        state = record_trade_closed(state, limits, -1).state
    assert state.losses_today == 3
    assert state.day_status == DayStatus.STOPPED_CAP  # stricter status retained
    with pytest.raises(ClearRejected):
        clear_stop(state, phrase=PHRASE, expected_phrase=PHRASE)


def test_interaction_loss_stop_then_kill_switch_keeps_loss_stop(armed, limits):
    state = _open_n(armed, limits, 3)
    for _ in range(3):
        state = record_trade_closed(state, limits, -1).state
    t = kill_switch(state)
    assert t.state.day_status == DayStatus.STOPPED_LOSSES
    assert t.events[0].event == "KILL_SWITCH"


def test_interaction_pnl_turns_negative_between_4th_and_5th(armed, limits, sure):
    state = replace(_open_n(armed, limits, 3), realized_pnl_today=100.0)
    assert evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW).allowed
    state = record_trade_opened(state, limits).state  # 4th
    state = record_trade_closed(state, limits, -150.0).state  # 4th loses, pnl now -50
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert not d.allowed and d.reason_code == "PNL_NOT_POSITIVE"


def test_interaction_manual_clear_then_new_loss_restops(armed, limits):
    # Manual stop cleared, then losses reach the limit -> STOPPED_LOSSES (loss_stop_cleared is False).
    state = clear_stop(kill_switch(armed).state, phrase=PHRASE, expected_phrase=PHRASE).state
    state = _open_n(state, limits, 3)
    for _ in range(3):
        state = record_trade_closed(state, limits, -1).state
    assert state.day_status == DayStatus.STOPPED_LOSSES


def test_interaction_full_day_walkthrough(armed, limits, sure, weak):
    events = []
    state = armed
    # 3 base trades: win, loss, win
    for pnl in (+500, -200, +300):
        d = evaluate_signal(state, limits, weak, strategy_eligible=True, now=NOW)
        assert d.allowed and d.tier == Tier.BASE
        t = record_trade_opened(state, limits)
        events += t.events
        t = record_trade_closed(t.state, limits, pnl)
        events += t.events
        state = t.state
    assert (state.trades_today, state.losses_today, state.realized_pnl_today) == (3, 1, 600)
    # 4th: weak signal blocked, sure-shot allowed
    assert evaluate_signal(state, limits, weak, strategy_eligible=True, now=NOW).reason_code == "NOT_SURE_SHOT"
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert d.allowed and d.tier == Tier.SURE_SHOT
    t = record_trade_opened(state, limits)
    events += t.events
    t = record_trade_closed(t.state, limits, -100)
    events += t.events
    state = t.state
    # 5th: pnl still positive (500), losses 2 -> allowed, then cap.
    d = evaluate_signal(state, limits, sure, strategy_eligible=True, now=NOW)
    assert d.allowed
    t = record_trade_opened(state, limits)
    events += t.events
    state = t.state
    assert state.day_status == DayStatus.STOPPED_CAP
    assert [e.event for e in events].count("TRADE_OPENED") == 5
    assert events[-1].event == "STOPPED_CAP"


def test_quality_defaults_never_pass(limits):
    ok, _ = is_sure_shot(SignalQuality(), limits.sure_shot)
    assert not ok
