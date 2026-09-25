"""Desk configuration. Every threshold lives here; nothing in the governor is a magic number."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIRM_PHRASE = "I ACCEPT THE RISK"


class DeskConfig(BaseSettings):
    """Loaded from environment variables (and an optional ``.env`` file)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- execution mode -------------------------------------------------------------------
    allow_live_orders: bool = Field(default=False, alias="ALLOW_LIVE_ORDERS")
    live_confirm_ttl_sec: int = Field(default=120, alias="DESK_LIVE_CONFIRM_TTL_SEC")
    confirm_phrase: str = Field(default=DEFAULT_CONFIRM_PHRASE, alias="DESK_CONFIRM_PHRASE")
    market_hours_only: bool = Field(default=True, alias="DESK_MARKET_HOURS_ONLY")
    allow_option_writing: bool = Field(default=False, alias="DESK_ALLOW_OPTION_WRITING")

    # --- sizing ---------------------------------------------------------------------------
    default_lots: int = Field(default=1, ge=1, alias="DESK_DEFAULT_LOTS")
    max_lots: int = Field(default=5, ge=1, alias="DESK_MAX_LOTS")
    product: str = Field(default="MIS", alias="DESK_PRODUCT")  # intraday by default
    entry_order_type: str = Field(default="MARKET", alias="DESK_ENTRY_ORDER_TYPE")

    # --- daily governor limits ------------------------------------------------------------
    max_trades_per_day: int = Field(default=5, ge=1, alias="DESK_MAX_TRADES_PER_DAY")
    max_losses_per_day: int = Field(default=3, ge=1, alias="DESK_MAX_LOSSES_PER_DAY")
    base_tier_trades: int = Field(default=3, ge=0, alias="DESK_BASE_TIER_TRADES")

    # --- sure-shot tier (trades base_tier_trades+1 .. max_trades_per_day) ------------------
    sure_shot_min_win_rate: float = Field(default=0.70, ge=0, le=1, alias="DESK_SURESHOT_MIN_WIN_RATE")
    sure_shot_min_sample_trades: int = Field(default=20, ge=1, alias="DESK_SURESHOT_MIN_SAMPLE_TRADES")
    sure_shot_min_oos_sharpe: float = Field(default=1.5, alias="DESK_SURESHOT_MIN_OOS_SHARPE")
    sure_shot_min_confidence_percentile: float = Field(
        default=0.90, ge=0, le=1, alias="DESK_SURESHOT_MIN_CONFIDENCE_PERCENTILE"
    )

    # --- strategy eligibility registry ----------------------------------------------------
    elig_min_backtest_trades: int = Field(default=30, ge=1, alias="DESK_ELIG_MIN_BACKTEST_TRADES")
    elig_min_oos_sharpe: float = Field(default=1.0, alias="DESK_ELIG_MIN_OOS_SHARPE")
    elig_min_win_rate: float = Field(default=0.50, ge=0, le=1, alias="DESK_ELIG_MIN_WIN_RATE")
    elig_max_drawdown_pct: float = Field(default=20.0, ge=0, alias="DESK_ELIG_MAX_DRAWDOWN_PCT")
    elig_max_test_age_days: int = Field(default=30, ge=1, alias="DESK_ELIG_MAX_TEST_AGE_DAYS")

    # --- persistence / api ------------------------------------------------------------------
    db_path: Path = Field(default=Path("data/desk.sqlite3"), alias="DESK_DB_PATH")
    api_token: str | None = Field(default=None, alias="DESK_API_TOKEN")

    # --- broker -----------------------------------------------------------------------------
    kite_api_key: str | None = Field(default=None, alias="KITE_API_KEY")
    kite_access_token: str | None = Field(default=None, alias="KITE_ACCESS_TOKEN")
    # Lot sizes used when the broker cannot tell us (paper mode). NSE revises these; override via env.
    lot_size_nifty: int = Field(default=75, alias="DESK_LOT_NIFTY")
    lot_size_banknifty: int = Field(default=35, alias="DESK_LOT_BANKNIFTY")
    lot_size_finnifty: int = Field(default=65, alias="DESK_LOT_FINNIFTY")
    lot_size_midcpnifty: int = Field(default=140, alias="DESK_LOT_MIDCPNIFTY")
    lot_size_default: int = Field(default=1, alias="DESK_LOT_DEFAULT")

    def lot_size_for(self, underlying: str) -> int:
        table = {
            "NIFTY": self.lot_size_nifty,
            "BANKNIFTY": self.lot_size_banknifty,
            "FINNIFTY": self.lot_size_finnifty,
            "MIDCPNIFTY": self.lot_size_midcpnifty,
        }
        return table.get(underlying.upper(), self.lot_size_default)

    def public_summary(self) -> dict:
        """Non-secret view of the configuration for the status endpoint."""
        return {
            "allow_live_orders": self.allow_live_orders,
            "market_hours_only": self.market_hours_only,
            "allow_option_writing": self.allow_option_writing,
            "default_lots": self.default_lots,
            "max_trades_per_day": self.max_trades_per_day,
            "max_losses_per_day": self.max_losses_per_day,
            "base_tier_trades": self.base_tier_trades,
            "sure_shot": {
                "min_win_rate": self.sure_shot_min_win_rate,
                "min_sample_trades": self.sure_shot_min_sample_trades,
                "min_oos_sharpe": self.sure_shot_min_oos_sharpe,
                "min_confidence_percentile": self.sure_shot_min_confidence_percentile,
            },
            "eligibility": {
                "min_backtest_trades": self.elig_min_backtest_trades,
                "min_oos_sharpe": self.elig_min_oos_sharpe,
                "min_win_rate": self.elig_min_win_rate,
                "max_drawdown_pct": self.elig_max_drawdown_pct,
                "max_test_age_days": self.elig_max_test_age_days,
            },
            "live_confirm_ttl_sec": self.live_confirm_ttl_sec,
        }
