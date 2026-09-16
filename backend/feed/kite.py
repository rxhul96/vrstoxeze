"""Optional live KiteTicker. Read-only. Single connection via MarketBus."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.config import get_settings
from backend.kite.readonly import ReadOnlyKite
from backend.safety.trading_disabled import TradingDisabledError, seal_kite_read_only

log = logging.getLogger("nifty.kite")

NIFTY_SPOT = "NSE:NIFTY 50"


class KiteLiveFeed:
    def __init__(self, bus: Any):
        self.bus = bus
        self.kite = ReadOnlyKite()
        self._task: asyncio.Task | None = None
        self.connected = False
        self.last_error: str | None = None

    def login_url(self) -> str | None:
        settings = get_settings()
        if not settings.kite_api_key:
            return None
        try:
            from kiteconnect import KiteConnect  # type: ignore
            k = seal_kite_read_only(KiteConnect(api_key=settings.kite_api_key))
            return k.login_url()
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return None

    def attach_token(self, token: str) -> None:
        settings = get_settings()
        try:
            from kiteconnect import KiteConnect  # type: ignore
            k = KiteConnect(api_key=settings.kite_api_key)
            k.set_access_token(token)
            self.kite.attach(k)
            self.connected = True
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.connected = False

    async def poll_quotes(self) -> dict | None:
        """REST fallback when websocket is down. Still read-only."""
        try:
            q = self.kite.ltp([NIFTY_SPOT])
            return q
        except TradingDisabledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return None
