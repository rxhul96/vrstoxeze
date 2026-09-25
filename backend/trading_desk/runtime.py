"""Builds the Trading Desk (engine + router + adapter) from the analyzer's settings.

* Paper broker by default. A live ``KiteBroker`` is constructed only when
  ``ALLOW_LIVE_ORDERS=true``; every live order still needs per-order operator confirmation.
* The desk shares the analyzer's Kite login: the access token obtained by ``/kite/callback``
  (or ``KITE_ACCESS_TOKEN`` / the saved ``.kite_token``) is pushed into the desk's own
  ``KiteConnect`` client. The analyzer's client stays sealed read-only; the desk's is the only
  one that can place orders.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from backend.config import Settings
from backend.paths import env_files
from backend.trading_desk.adapter import AdapterSettings, SignalAdapter
from optionsdesk.api import build_desk_router
from optionsdesk.brokers.base import BrokerAdapter, BrokerError
from optionsdesk.brokers.paper import PaperBroker
from optionsdesk.clock import IST, session_day
from optionsdesk.config import DeskConfig
from optionsdesk.engine import DeskEngine
from optionsdesk.store import DeskStore

log = logging.getLogger("nifty.desk")


def resolve_kite_token(settings: Settings) -> str | None:
    """Analyzer's current Kite access token: env first, then the file ``/kite/callback`` writes."""
    if settings.kite_access_token:
        return settings.kite_access_token
    if settings.data_dir and (settings.data_dir / ".kite_token").exists():
        return (settings.data_dir / ".kite_token").read_text(encoding="utf-8").strip() or None
    return None


def build_desk_config(settings: Settings) -> DeskConfig:
    overrides: dict[str, Any] = {}
    if not os.environ.get("DESK_DB_PATH") and settings.data_dir:
        overrides["DESK_DB_PATH"] = str(settings.data_dir / "desk.sqlite3")
    if settings.kite_api_key:
        overrides["KITE_API_KEY"] = settings.kite_api_key
    token = resolve_kite_token(settings)
    if token:
        overrides["KITE_ACCESS_TOKEN"] = token
    return DeskConfig(_env_file=env_files() or None, **overrides)


def _select_broker(cfg: DeskConfig) -> tuple[BrokerAdapter, str | None]:
    """Paper unless live orders are explicitly allowed *and* a Kite broker can be built."""
    if not cfg.allow_live_orders:
        return PaperBroker(), None
    if not cfg.kite_api_key:
        reason = "ALLOW_LIVE_ORDERS=true but KITE_API_KEY is missing; desk stays in PAPER mode"
        log.error(reason)
        return PaperBroker(), reason
    try:
        from optionsdesk.brokers.kite import KiteBroker

        broker = KiteBroker(cfg.kite_api_key, cfg.kite_access_token or "")
    except BrokerError as exc:
        reason = f"ALLOW_LIVE_ORDERS=true but the Kite broker is unavailable ({exc}); desk stays in PAPER mode"
        log.error(reason)
        return PaperBroker(), reason
    log.warning("TRADING DESK: LIVE ORDERS ENABLED — every order requires operator confirmation")
    return broker, None


class DeskRuntime:
    def __init__(
        self,
        settings: Settings,
        config: DeskConfig,
        engine: DeskEngine,
        adapter: SignalAdapter,
        live_fallback: str | None = None,
    ) -> None:
        self.settings = settings
        self.config = config
        self.engine = engine
        self.adapter = adapter
        self.live_fallback = live_fallback
        self.kite_token: str | None = config.kite_access_token or None
        self.router = build_desk_router(engine)
        self.registered = adapter.register_strategies()
        if self.registered:
            log.info("desk: registered strategies %s (NOT_TESTED until backtests are posted)", self.registered)

    @classmethod
    def build(
        cls,
        settings: Settings,
        *,
        adapter_settings: AdapterSettings | None = None,
        store: DeskStore | None = None,
    ) -> DeskRuntime:
        cfg = build_desk_config(settings)
        broker, fallback = _select_broker(cfg)
        engine = DeskEngine(cfg, store or DeskStore(cfg.db_path), broker)
        adapter = SignalAdapter(engine, adapter_settings)
        rt = cls(settings, cfg, engine, adapter, fallback)
        log.info("Trading Desk mounted at /desk — mode=%s broker=%s", engine.mode, engine.broker.name)
        return rt

    # -- shared Kite session ------------------------------------------------------------------

    def attach_kite_token(self, token: str) -> None:
        """Reuse the analyzer's Kite login for the desk's broker (one login for both)."""
        self.kite_token = token
        broker = self.engine.broker
        client = getattr(broker, "kite", None)
        if broker.is_live and client is not None:
            client.set_access_token(token)
            log.info("desk: Kite session attached from analyzer login")

    # -- exits in live mode -------------------------------------------------------------------

    def poll_prices(self) -> None:
        """Live mode only: pull LTPs for open trades so SL/target exits fire without a tick feed."""
        if self.engine.mode == "live":
            self.engine.poll_prices()

    # -- status -------------------------------------------------------------------------------

    def summary(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(tz=IST)
        st = self.engine.state
        return {
            "mounted": True,
            "path": "/desk",
            "mode": self.engine.mode,
            "broker": self.engine.broker.name,
            "allow_live_orders": self.config.allow_live_orders,
            "live_fallback": self.live_fallback,
            "armed": st.is_armed(session_day(now)),
            "day_status": st.day_status.value,
            "trades_today": st.trades_today,
            "losses_today": st.losses_today,
            "kite_session": "shared" if self.kite_token else "none",
            "db_path": str(self.config.db_path),
            "adapter": self.adapter.summary(),
        }
