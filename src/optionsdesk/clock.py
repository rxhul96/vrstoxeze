"""IST clock helpers. The governor's day resets at 09:15 IST (NSE cash/F&O open)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SESSION_RESET = time(9, 15)
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=IST)


class FixedClock:
    """Deterministic clock for tests; ``advance`` moves it forward."""

    def __init__(self, at: datetime) -> None:
        self._at = to_ist(at)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = to_ist(at)

    def advance(self, **kwargs) -> None:
        self._at = self._at + timedelta(**kwargs)


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def session_day(now: datetime) -> date:
    """The governor 'day' a timestamp belongs to.

    Counters reset at 09:15 IST, so 08:59 still belongs to the previous session day.
    """
    now = to_ist(now)
    if now.time() < SESSION_RESET:
        return now.date() - timedelta(days=1)
    return now.date()


def is_market_open(now: datetime) -> bool:
    now = to_ist(now)
    if now.weekday() >= 5:  # Sat/Sun; exchange holidays are the host app's concern
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE
