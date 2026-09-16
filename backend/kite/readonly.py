"""Read-only Kite wrapper. Execution methods are physically absent."""
from __future__ import annotations

from typing import Any

from backend.safety.trading_disabled import (
    EXECUTION_METHODS,
    READ_METHODS,
    TradingDisabledError,
    seal_kite_read_only,
)


class ReadOnlyKite:
    """Exposes only market-data reads. No order methods exist on this type."""

    def __init__(self, inner: Any | None = None):
        self._inner = seal_kite_read_only(inner) if inner is not None else None

    def attach(self, inner: Any) -> None:
        self._inner = seal_kite_read_only(inner)

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name in EXECUTION_METHODS:
            raise TradingDisabledError(f"SIGNAL-ONLY MODE — {name} is not available.")
        if name not in READ_METHODS:
            raise AttributeError(name)
        if self._inner is None:
            raise RuntimeError("Kite client is not connected.")
        fn = getattr(self._inner, name)
        return fn(*args, **kwargs)

    def quote(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("quote", *args, **kwargs)

    def ltp(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("ltp", *args, **kwargs)

    def ohlc(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("ohlc", *args, **kwargs)

    def historical_data(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("historical_data", *args, **kwargs)

    def instruments(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("instruments", *args, **kwargs)

    def profile(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("profile", *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name in EXECUTION_METHODS:
            raise TradingDisabledError(
                f"SIGNAL-ONLY MODE — Kite.{name} is not available on this analyzer."
            )
        raise AttributeError(name)
