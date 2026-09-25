"""Build Kite NFO option tradingsymbols for the analyzer's index signals.

The analyzer reasons about NIFTY spot; the desk only accepts NSE option tradingsymbols.
This module picks the nearest expiry and renders the Kite symbol format:

* weekly  ``NIFTY25O0725000CE``  -> underlying YY M DD strike CE/PE (M = 1-9, O, N, D)
* monthly ``NIFTY25SEP25000CE``  -> underlying YY MON strike CE/PE (last expiry of the month)
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable

from backend.market import is_trading_day

MARKET_CLOSE = time(15, 30)
_MONTH_CODES = "123456789OND"
_MONTH_NAMES = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def next_expiry(
    now: datetime,
    expiry_weekday: int,
    trading_day: Callable[[date], bool] = is_trading_day,
) -> tuple[date, bool]:
    """Return ``(expiry_date, is_monthly)`` for the nearest contract still tradable at ``now``.

    If the scheduled weekday is a holiday NSE brings the expiry forward to the previous trading
    day. A contract that already expired today (after 15:30) rolls to next week.
    """
    today = now.date()
    scheduled = today + timedelta(days=(expiry_weekday - today.weekday()) % 7)
    while True:
        actual = scheduled
        while not trading_day(actual):
            actual -= timedelta(days=1)
        expired = actual < today or (actual == today and now.time() > MARKET_CLOSE)
        if not expired:
            monthly = (scheduled + timedelta(days=7)).month != scheduled.month
            return actual, monthly
        scheduled += timedelta(days=7)


def option_symbol(underlying: str, expiry: date, monthly: bool, strike: float, kind: str) -> str:
    kind = kind.upper()
    if kind not in ("CE", "PE"):
        raise ValueError(f"option kind must be CE or PE, got {kind!r}")
    strike_txt = str(int(strike)) if float(strike).is_integer() else f"{strike:g}"
    yy = expiry.strftime("%y")
    if monthly:
        return f"{underlying.upper()}{yy}{_MONTH_NAMES[expiry.month - 1]}{strike_txt}{kind}"
    return f"{underlying.upper()}{yy}{_MONTH_CODES[expiry.month - 1]}{expiry.day:02d}{strike_txt}{kind}"


def atm_strike(spot: float, step: int = 50) -> int:
    return int(round(spot / step) * step)
