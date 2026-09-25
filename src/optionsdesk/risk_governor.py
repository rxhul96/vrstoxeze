"""Risk governor — pure functions over an immutable daily :class:`RiskState`.

Nothing here touches a database, a broker or the wall clock. Every function returns a new
state plus the list of :class:`RiskEvent` rows that the caller must persist (append-only).

Rules (numbers refer to the product spec):

1. ``trades_today >= max_trades_per_day``  -> block, ``STOPPED_CAP``; never overridable.
2. ``losses_today >= max_losses_per_day``  -> block, ``STOPPED_LOSSES``; never auto-resumes;
   manual clear needs the confirmation phrase and is logged.
3. trades ``1..base_tier_trades`` are allowed once the desk is armed for the day and the signal
   passes eligibility.
4. trades ``base_tier_trades+1 .. max_trades_per_day`` only if ``realized_pnl_today > 0`` AND
   ``losses_today < max_losses_per_day`` AND the signal meets the sure-shot thresholds.
5. Kill switch -> ``STOPPED_MANUAL`` (the engine cancels orders and flattens positions).
6. Every state transition yields a :class:`RiskEvent`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime

from optionsdesk.clock import session_day
from optionsdesk.config import DeskConfig
from optionsdesk.models import DayStatus, RiskEvent, Tier

# Higher number = stricter. Transitions never move to a *less* strict stop automatically.
_STATUS_RANK = {
    DayStatus.ACTIVE: 0,
    DayStatus.STOPPED_MANUAL: 1,
    DayStatus.STOPPED_LOSSES: 2,
    DayStatus.STOPPED_CAP: 3,
}


@dataclass(frozen=True)
class SureShotThresholds:
    min_win_rate: float = 0.70
    min_sample_trades: int = 20
    min_oos_sharpe: float = 1.5
    min_confidence_percentile: float = 0.90


@dataclass(frozen=True)
class RiskLimits:
    max_trades_per_day: int = 5
    max_losses_per_day: int = 3
    base_tier_trades: int = 3
    sure_shot: SureShotThresholds = field(default_factory=SureShotThresholds)

    @classmethod
    def from_config(cls, cfg: DeskConfig) -> RiskLimits:
        return cls(
            max_trades_per_day=cfg.max_trades_per_day,
            max_losses_per_day=cfg.max_losses_per_day,
            base_tier_trades=cfg.base_tier_trades,
            sure_shot=SureShotThresholds(
                min_win_rate=cfg.sure_shot_min_win_rate,
                min_sample_trades=cfg.sure_shot_min_sample_trades,
                min_oos_sharpe=cfg.sure_shot_min_oos_sharpe,
                min_confidence_percentile=cfg.sure_shot_min_confidence_percentile,
            ),
        )


@dataclass(frozen=True)
class SignalQuality:
    """Inputs to the sure-shot test. ``None`` means "unknown", which never passes."""

    live_win_rate: float | None = None
    live_trades: int | None = None
    oos_sharpe: float | None = None
    confidence_percentile: float | None = None


@dataclass(frozen=True)
class RiskState:
    trading_day: date
    armed_for_day: date | None = None
    trades_today: int = 0
    losses_today: int = 0
    realized_pnl_today: float = 0.0
    day_status: DayStatus = DayStatus.ACTIVE
    loss_stop_cleared: bool = False

    def is_armed(self, today: date) -> bool:
        return self.armed_for_day == today

    def to_dict(self) -> dict:
        return {
            "trading_day": self.trading_day.isoformat(),
            "armed_for_day": self.armed_for_day.isoformat() if self.armed_for_day else None,
            "trades_today": self.trades_today,
            "losses_today": self.losses_today,
            "realized_pnl_today": round(self.realized_pnl_today, 2),
            "day_status": self.day_status.value,
            "loss_stop_cleared": self.loss_stop_cleared,
        }


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason_code: str
    reason: str
    state: RiskState
    events: tuple[RiskEvent, ...] = ()
    tier: Tier | None = None


@dataclass(frozen=True)
class Transition:
    state: RiskState
    events: tuple[RiskEvent, ...] = ()


def fresh_state(trading_day: date) -> RiskState:
    return RiskState(trading_day=trading_day)


def _event(
    prev: RiskState,
    new: RiskState,
    event: str,
    *,
    actor: str = "system",
    reason: str = "",
    signal_id: int | None = None,
    trade_id: int | None = None,
    details: dict | None = None,
) -> RiskEvent:
    return RiskEvent(
        trading_day=new.trading_day,
        event=event,
        from_status=prev.day_status,
        to_status=new.day_status,
        trades_today=new.trades_today,
        losses_today=new.losses_today,
        realized_pnl_today=round(new.realized_pnl_today, 2),
        actor=actor,
        reason=reason,
        signal_id=signal_id,
        trade_id=trade_id,
        details=details or {},
    )


def _stricter(current: DayStatus, proposed: DayStatus) -> DayStatus:
    return proposed if _STATUS_RANK[proposed] > _STATUS_RANK[current] else current


# --------------------------------------------------------------------------------------------
# Day lifecycle
# --------------------------------------------------------------------------------------------


def roll_day(state: RiskState, now: datetime) -> Transition:
    """Reset counters when a new session day (09:15 IST boundary) has started."""
    today = session_day(now)
    if today == state.trading_day:
        return Transition(state)
    new = fresh_state(today)
    ev = _event(
        state,
        new,
        "DAY_RESET",
        reason=f"new session day {today.isoformat()} (previous {state.trading_day.isoformat()})",
        details={"previous": state.to_dict()},
    )
    # The event belongs to the new day but records the previous status as from_status.
    return Transition(new, (ev,))


def arm(state: RiskState, today: date, actor: str = "operator") -> Transition:
    if state.is_armed(today):
        return Transition(state)
    new = replace(state, armed_for_day=today)
    return Transition(new, (_event(state, new, "ARMED", actor=actor, reason=f"armed for {today.isoformat()}"),))


def disarm(state: RiskState, actor: str = "operator") -> Transition:
    if state.armed_for_day is None:
        return Transition(state)
    new = replace(state, armed_for_day=None)
    return Transition(new, (_event(state, new, "DISARMED", actor=actor),))


# --------------------------------------------------------------------------------------------
# Rule evaluation
# --------------------------------------------------------------------------------------------


def is_sure_shot(quality: SignalQuality, thresholds: SureShotThresholds) -> tuple[bool, str]:
    """Rule 4 quality gate. Returns ``(passes, reason)``."""
    if quality.live_trades is None or quality.live_trades < thresholds.min_sample_trades:
        return False, (
            f"live sample {quality.live_trades} < {thresholds.min_sample_trades} trades required for sure-shot"
        )
    if quality.live_win_rate is None or quality.live_win_rate < thresholds.min_win_rate:
        return False, f"live win rate {quality.live_win_rate} < {thresholds.min_win_rate:.0%}"
    if quality.oos_sharpe is None or quality.oos_sharpe < thresholds.min_oos_sharpe:
        return False, f"OOS Sharpe {quality.oos_sharpe} < {thresholds.min_oos_sharpe}"
    if (
        quality.confidence_percentile is None
        or quality.confidence_percentile < thresholds.min_confidence_percentile
    ):
        return False, (
            f"confidence percentile {quality.confidence_percentile} < {thresholds.min_confidence_percentile}"
        )
    return True, "meets sure-shot thresholds"


def evaluate_signal(
    state: RiskState,
    limits: RiskLimits,
    quality: SignalQuality,
    *,
    strategy_eligible: bool,
    now: datetime,
    signal_id: int | None = None,
) -> Decision:
    """Decide whether a signal may open a new trade right now.

    The returned ``state`` may differ from the input when a limit was found already breached
    (e.g. a stale ACTIVE status with ``trades_today >= cap``); callers must persist it.
    """
    today = session_day(now)
    if today != state.trading_day:
        return Decision(False, "DAY_NOT_ROLLED", "risk state belongs to a different session day; roll first", state)

    if state.day_status != DayStatus.ACTIVE:
        return Decision(False, state.day_status.value, f"desk is {state.day_status.value}", state)

    if not state.is_armed(today):
        return Decision(False, "NOT_ARMED", "desk is not armed for today; arm it from the UI first", state)

    # Rule 1 — hard daily cap (defensive: normally record_trade_opened already flipped the status).
    if state.trades_today >= limits.max_trades_per_day:
        new = replace(state, day_status=DayStatus.STOPPED_CAP)
        ev = _event(
            state, new, "STOPPED_CAP", reason=f"{state.trades_today} trades >= cap {limits.max_trades_per_day}",
            signal_id=signal_id,
        )
        return Decision(False, "TRADE_CAP", f"daily trade cap {limits.max_trades_per_day} reached", new, (ev,))

    # Rule 2 — loss stop (defensive path; record_trade_closed normally flips it).
    if state.losses_today >= limits.max_losses_per_day and not state.loss_stop_cleared:
        new = replace(state, day_status=DayStatus.STOPPED_LOSSES)
        ev = _event(
            state, new, "STOPPED_LOSSES",
            reason=f"{state.losses_today} losses >= limit {limits.max_losses_per_day}", signal_id=signal_id,
        )
        return Decision(False, "LOSS_LIMIT", f"daily loss limit {limits.max_losses_per_day} reached", new, (ev,))

    if not strategy_eligible:
        return Decision(False, "STRATEGY_NOT_ELIGIBLE", "strategy is not eligible (not tested / failed / stale)", state)

    # Rule 3 — base tier.
    if state.trades_today < limits.base_tier_trades:
        n = state.trades_today + 1
        return Decision(True, "BASE_TIER", f"trade {n} of {limits.base_tier_trades} base-tier trades", state, tier=Tier.BASE)

    # Rule 4 — sure-shot tier.
    n = state.trades_today + 1
    if state.realized_pnl_today <= 0:
        return Decision(
            False, "PNL_NOT_POSITIVE",
            f"trade {n} needs realized PnL > 0 (currently {state.realized_pnl_today:.2f})", state,
        )
    if state.losses_today >= limits.max_losses_per_day:
        return Decision(
            False, "LOSSES_AT_LIMIT",
            f"trade {n} needs losses < {limits.max_losses_per_day} (currently {state.losses_today})", state,
        )
    ok, why = is_sure_shot(quality, limits.sure_shot)
    if not ok:
        return Decision(False, "NOT_SURE_SHOT", f"trade {n} requires a sure-shot signal: {why}", state)
    return Decision(True, "SURE_SHOT_TIER", f"trade {n}: {why}", state, tier=Tier.SURE_SHOT)


# --------------------------------------------------------------------------------------------
# Recording outcomes
# --------------------------------------------------------------------------------------------


def record_trade_opened(
    state: RiskState, limits: RiskLimits, *, trade_id: int | None = None, signal_id: int | None = None
) -> Transition:
    new = replace(state, trades_today=state.trades_today + 1)
    events = [_event(state, new, "TRADE_OPENED", trade_id=trade_id, signal_id=signal_id)]
    if new.trades_today >= limits.max_trades_per_day:
        stopped = replace(new, day_status=_stricter(new.day_status, DayStatus.STOPPED_CAP))
        if stopped.day_status != new.day_status:
            events.append(
                _event(
                    new, stopped, "STOPPED_CAP",
                    reason=f"trade cap {limits.max_trades_per_day} reached", trade_id=trade_id,
                )
            )
        new = stopped
    return Transition(new, tuple(events))


def record_trade_closed(
    state: RiskState, limits: RiskLimits, realized_pnl: float, *, trade_id: int | None = None
) -> Transition:
    is_loss = realized_pnl < 0
    new = replace(
        state,
        realized_pnl_today=state.realized_pnl_today + realized_pnl,
        losses_today=state.losses_today + (1 if is_loss else 0),
    )
    events = [
        _event(
            state, new, "TRADE_CLOSED", trade_id=trade_id,
            reason=("loss" if is_loss else "win/flat") + f" {realized_pnl:+.2f}",
            details={"realized_pnl": round(realized_pnl, 2), "is_loss": is_loss},
        )
    ]
    if is_loss and new.losses_today >= limits.max_losses_per_day and not new.loss_stop_cleared:
        stopped = replace(new, day_status=_stricter(new.day_status, DayStatus.STOPPED_LOSSES))
        if stopped.day_status != new.day_status:
            events.append(
                _event(
                    new, stopped, "STOPPED_LOSSES",
                    reason=f"loss limit {limits.max_losses_per_day} reached", trade_id=trade_id,
                )
            )
        new = stopped
    return Transition(new, tuple(events))


# --------------------------------------------------------------------------------------------
# Manual controls
# --------------------------------------------------------------------------------------------


def kill_switch(state: RiskState, actor: str = "operator", reason: str = "kill switch") -> Transition:
    target = _stricter(state.day_status, DayStatus.STOPPED_MANUAL)
    new = replace(state, day_status=target)
    # Always log the kill even if the status was already stricter — the engine still flattens.
    return Transition(new, (_event(state, new, "KILL_SWITCH", actor=actor, reason=reason),))


class ClearRejected(ValueError):
    pass


def clear_stop(
    state: RiskState, *, phrase: str, expected_phrase: str, actor: str = "operator", note: str = ""
) -> Transition:
    """Manually clear ``STOPPED_LOSSES`` or ``STOPPED_MANUAL``. ``STOPPED_CAP`` can never be cleared."""
    if state.day_status == DayStatus.ACTIVE:
        raise ClearRejected("desk is already ACTIVE")
    if state.day_status == DayStatus.STOPPED_CAP:
        raise ClearRejected("STOPPED_CAP is final for the day and cannot be cleared")
    if phrase.strip() != expected_phrase:
        raise ClearRejected("confirmation phrase does not match")
    cleared_losses = state.day_status == DayStatus.STOPPED_LOSSES
    new = replace(
        state,
        day_status=DayStatus.ACTIVE,
        loss_stop_cleared=state.loss_stop_cleared or cleared_losses,
    )
    ev = _event(
        state, new, "STOP_CLEARED", actor=actor,
        reason=f"manual clear of {state.day_status.value}" + (f": {note}" if note else ""),
        details={"phrase_ok": True, "cleared": state.day_status.value},
    )
    return Transition(new, (ev,))
