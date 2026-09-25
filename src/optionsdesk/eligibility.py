"""Strategy eligibility registry.

A strategy may trade only when it is ``ELIGIBLE``:

* ``NOT_TESTED`` — never registered, or registered without backtest results.
* ``STALE``      — the signal's ``code_hash`` differs from the tested hash, or the test is older
                   than ``elig_max_test_age_days``.
* ``FAILED``     — tested, but below the configured thresholds.
* ``ELIGIBLE``   — tested, fresh, and above thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from optionsdesk.clock import to_ist
from optionsdesk.config import DeskConfig
from optionsdesk.models import EligibilityStatus, StrategyRecord, StrategyRegistration
from optionsdesk.store import DeskStore


@dataclass(frozen=True)
class EligibilityThresholds:
    min_backtest_trades: int = 30
    min_oos_sharpe: float = 1.0
    min_win_rate: float = 0.50
    max_drawdown_pct: float = 20.0
    max_test_age_days: int = 30

    @classmethod
    def from_config(cls, cfg: DeskConfig) -> EligibilityThresholds:
        return cls(
            min_backtest_trades=cfg.elig_min_backtest_trades,
            min_oos_sharpe=cfg.elig_min_oos_sharpe,
            min_win_rate=cfg.elig_min_win_rate,
            max_drawdown_pct=cfg.elig_max_drawdown_pct,
            max_test_age_days=cfg.elig_max_test_age_days,
        )


def classify(
    reg: StrategyRegistration | None,
    thresholds: EligibilityThresholds,
    *,
    now: datetime,
    signal_code_hash: str | None = None,
) -> tuple[EligibilityStatus, str]:
    """Pure classification. ``signal_code_hash`` (when given) must match the tested hash."""
    if reg is None:
        return EligibilityStatus.NOT_TESTED, "strategy is not registered"
    if reg.backtest is None or reg.tested_at is None:
        return EligibilityStatus.NOT_TESTED, "no backtest results recorded"
    if signal_code_hash is not None and signal_code_hash != reg.code_hash:
        return EligibilityStatus.STALE, (
            f"signal code_hash {signal_code_hash[:12]} != tested {reg.code_hash[:12]}; re-test required"
        )
    age = to_ist(now) - to_ist(reg.tested_at)
    if age > timedelta(days=thresholds.max_test_age_days):
        return EligibilityStatus.STALE, f"backtest is {age.days} days old (> {thresholds.max_test_age_days})"
    bt = reg.backtest
    failures = []
    if bt.trades < thresholds.min_backtest_trades:
        failures.append(f"trades {bt.trades} < {thresholds.min_backtest_trades}")
    if bt.oos_sharpe < thresholds.min_oos_sharpe:
        failures.append(f"OOS Sharpe {bt.oos_sharpe} < {thresholds.min_oos_sharpe}")
    if bt.win_rate < thresholds.min_win_rate:
        failures.append(f"win rate {bt.win_rate:.0%} < {thresholds.min_win_rate:.0%}")
    if bt.max_drawdown_pct > thresholds.max_drawdown_pct:
        failures.append(f"max drawdown {bt.max_drawdown_pct}% > {thresholds.max_drawdown_pct}%")
    if failures:
        return EligibilityStatus.FAILED, "; ".join(failures)
    return EligibilityStatus.ELIGIBLE, "passes eligibility thresholds"


class StrategyRegistry:
    def __init__(self, store: DeskStore, thresholds: EligibilityThresholds) -> None:
        self.store = store
        self.thresholds = thresholds

    def register(self, reg: StrategyRegistration, now: datetime) -> StrategyRecord:
        self.store.upsert_strategy(reg, now)
        return self.get(reg.strategy_id, now)  # type: ignore[return-value]

    def status_for_signal(
        self, strategy_id: str, code_hash: str | None, now: datetime
    ) -> tuple[EligibilityStatus, str]:
        found = self.store.get_strategy(strategy_id)
        reg = found[0] if found else None
        return classify(reg, self.thresholds, now=now, signal_code_hash=code_hash)

    def get(self, strategy_id: str, now: datetime) -> StrategyRecord | None:
        found = self.store.get_strategy(strategy_id)
        if not found:
            return None
        reg, updated_at = found
        status, reason = classify(reg, self.thresholds, now=now)
        return StrategyRecord(**reg.model_dump(), status=status, status_reason=reason, updated_at=updated_at)

    def list(self, now: datetime) -> list[StrategyRecord]:
        out = []
        for reg, updated_at in self.store.list_strategies():
            status, reason = classify(reg, self.thresholds, now=now)
            out.append(StrategyRecord(**reg.model_dump(), status=status, status_reason=reason, updated_at=updated_at))
        return out
