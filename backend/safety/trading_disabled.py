"""HARD DISABLE: this analyzer never places, modifies, or cancels broker orders.

Kite/Zerodha may be used only for read operations (LTP, OHLC, history, quotes,
instruments, depth, WebSocket ticks). AI agents must never receive execution tools.
"""
from __future__ import annotations

from typing import Any, Callable

TRADING_EXECUTION_ENABLED = False

EXECUTION_METHODS = frozenset({
    "place_order",
    "modify_order",
    "cancel_order",
    "exit_order",
    "execute_order",
    "place_gtt",
    "modify_gtt",
    "delete_gtt",
    "place_mf_order",
    "cancel_mf_order",
    "place_order_bo",
    "place_order_co",
    "convert_position",
    "square_off",
})

READ_METHODS = frozenset({
    "quote", "ltp", "ohlc", "historical_data", "instruments", "profile",
    "margins", "holdings", "positions", "orders", "order_history",
    "set_access_token", "generate_session", "login_url",
})

_REASON = (
    "SIGNAL-ONLY MODE — automated trading is disabled. "
    "This analyzer never places, modifies, or cancels broker orders."
)


class TradingDisabledError(RuntimeError):
    """Raised if any code tries to call a broker execution method."""


def refuse_execution(action: str = "place") -> dict:
    return {
        "ok": False,
        "reason": _REASON,
        "action": action,
        "would_place_order": False,
        "execution_enabled": False,
        "mode": "signal-only",
    }


def _blocked(name: str) -> Callable[..., Any]:
    def _inner(*_args: Any, **_kwargs: Any) -> Any:
        raise TradingDisabledError(
            f"SIGNAL-ONLY MODE — Kite.{name} is not available on this analyzer."
        )
    _inner.__name__ = name
    return _inner


def seal_kite_read_only(kite: Any) -> Any:
    """Replace broker execution methods on a KiteConnect-like object."""
    if kite is None:
        return kite
    for name in EXECUTION_METHODS:
        try:
            setattr(kite, name, _blocked(name))
        except Exception:  # noqa: BLE001
            pass
    return kite


def is_execution_method(name: str) -> bool:
    return name in EXECUTION_METHODS
