from __future__ import annotations

from datetime import date, datetime

import pytest

from optionsdesk.clock import IST
from optionsdesk.risk_governor import RiskLimits, RiskState, SignalQuality, SureShotThresholds

TODAY = date(2026, 9, 25)  # a Friday
NOW = datetime(2026, 9, 25, 10, 0, tzinfo=IST)


@pytest.fixture
def limits() -> RiskLimits:
    return RiskLimits(
        max_trades_per_day=5,
        max_losses_per_day=3,
        base_tier_trades=3,
        sure_shot=SureShotThresholds(
            min_win_rate=0.70, min_sample_trades=20, min_oos_sharpe=1.5, min_confidence_percentile=0.90
        ),
    )


@pytest.fixture
def armed() -> RiskState:
    return RiskState(trading_day=TODAY, armed_for_day=TODAY)


@pytest.fixture
def sure() -> SignalQuality:
    return SignalQuality(live_win_rate=0.8, live_trades=40, oos_sharpe=2.0, confidence_percentile=0.95)


@pytest.fixture
def weak() -> SignalQuality:
    return SignalQuality(live_win_rate=0.55, live_trades=40, oos_sharpe=1.0, confidence_percentile=0.5)
