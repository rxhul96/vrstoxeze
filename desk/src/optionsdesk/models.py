"""Pydantic models shared by the governor, engine, brokers and API."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DayStatus(StrEnum):
    ACTIVE = "ACTIVE"
    STOPPED_LOSSES = "STOPPED_LOSSES"
    STOPPED_CAP = "STOPPED_CAP"
    STOPPED_MANUAL = "STOPPED_MANUAL"


class Direction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class Tier(StrEnum):
    BASE = "BASE"
    SURE_SHOT = "SURE_SHOT"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_TESTED = "NOT_TESTED"
    FAILED = "FAILED"
    STALE = "STALE"


class TradeStatus(StrEnum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"  # live mode: waiting for operator confirmation
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ExitReason(StrEnum):
    TARGET = "TARGET"
    STOP_LOSS = "STOP_LOSS"
    MANUAL = "MANUAL"
    KILL_SWITCH = "KILL_SWITCH"


class StrategyStats(BaseModel):
    """Live performance stats the analyzer knows about a strategy (used for the sure-shot tier)."""

    live_win_rate: float | None = Field(default=None, ge=0, le=1)
    live_trades: int | None = Field(default=None, ge=0)
    oos_sharpe: float | None = None
    confidence_percentile: float | None = Field(default=None, ge=0, le=1)


class SignalIn(BaseModel):
    """Payload accepted by ``POST /desk/signals`` and ``DeskEngine.submit_signal``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    strategy_id: str = Field(min_length=1, max_length=64)
    code_hash: str | None = Field(default=None, max_length=128)
    tradingsymbol: str = Field(min_length=3, max_length=40)
    exchange: str = Field(default="NFO", max_length=10)
    direction: Direction
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    lots: int | None = Field(default=None, ge=1)
    stats: StrategyStats = Field(default_factory=StrategyStats)
    note: str | None = Field(default=None, max_length=500)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tradingsymbol", "exchange")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.upper() if v else v


class SignalRecord(BaseModel):
    id: int
    received_at: datetime
    payload: SignalIn
    accepted: bool
    tier: Tier | None
    reason_code: str
    reason: str
    eligibility: EligibilityStatus
    trade_id: int | None = None


class RiskEvent(BaseModel):
    """One immutable audit row. ``id``/``created_at`` are assigned by the store."""

    id: int | None = None
    created_at: datetime | None = None
    trading_day: date
    event: str
    from_status: DayStatus
    to_status: DayStatus
    trades_today: int
    losses_today: int
    realized_pnl_today: float
    actor: str = "system"
    reason: str = ""
    signal_id: int | None = None
    trade_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OrderRequest(BaseModel):
    tradingsymbol: str
    exchange: str = "NFO"
    transaction_type: Direction
    quantity: int = Field(gt=0)
    order_type: str = "MARKET"
    price: float | None = None
    product: str = "MIS"
    tag: str | None = None


class OrderResult(BaseModel):
    order_id: str
    status: str  # COMPLETE | OPEN | REJECTED | CANCELLED
    filled_quantity: int = 0
    average_price: float | None = None
    message: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Position(BaseModel):
    tradingsymbol: str
    exchange: str
    quantity: int  # signed net quantity
    average_price: float
    last_price: float | None = None
    pnl: float | None = None
    product: str = "MIS"


class Trade(BaseModel):
    id: int
    signal_id: int
    strategy_id: str
    tradingsymbol: str
    underlying: str
    direction: Direction
    lots: int
    quantity: int
    tier: Tier
    mode: str  # paper | live
    status: TradeStatus
    entry_price: float
    stop_loss: float
    target: float
    fill_price: float | None = None
    exit_price: float | None = None
    exit_reason: ExitReason | None = None
    realized_pnl: float | None = None
    entry_order_id: str | None = None
    exit_order_id: str | None = None
    created_at: datetime
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    confirm_deadline: datetime | None = None
    note: str | None = None


class BacktestResult(BaseModel):
    oos_sharpe: float
    win_rate: float = Field(ge=0, le=1)
    trades: int = Field(ge=0)
    max_drawdown_pct: float = Field(default=0.0, ge=0)


class StrategyRegistration(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=64)
    code_hash: str = Field(min_length=1, max_length=128)
    backtest: BacktestResult | None = None
    tested_at: datetime | None = None
    description: str | None = Field(default=None, max_length=300)


class StrategyRecord(StrategyRegistration):
    status: EligibilityStatus
    status_reason: str
    updated_at: datetime
