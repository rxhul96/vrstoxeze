"""NSE market-hours helper (IST) plus holiday calendar."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
PREOPEN = time(9, 0)
OPEN = time(9, 15)
CLOSE = time(15, 30)
CLOSING_SESSION_OPEN = time(15, 40)
CLOSING_SESSION_CLOSE = time(16, 0)

# Session runner clock (IST)
INIT = time(8, 30)
KITE_AUTH = time(8, 40)
SYNC_INSTRUMENTS = time(8, 45)
PREMARKET = time(9, 0)
COLLECT_START = time(9, 15)
COLLECT_STOP = time(15, 30)
FINALIZE = time(15, 35)
DAILY_REPORT = time(16, 0)
ARCHIVE = time(16, 30)

HOLIDAYS_PATH = Path(__file__).parent / "session" / "holidays.json"


def now_ist() -> datetime:
    return datetime.now(IST)


@lru_cache
def _holiday_set() -> set[date]:
    if not HOLIDAYS_PATH.exists():
        return set()
    raw = json.loads(HOLIDAYS_PATH.read_text(encoding="utf-8"))
    out: set[date] = set()
    for item in raw.get("holidays", []):
        try:
            out.add(date.fromisoformat(item))
        except ValueError:
            continue
    return out


def is_nse_holiday(dt: datetime | date | None = None) -> bool:
    if dt is None:
        dt = now_ist()
    d = dt.date() if isinstance(dt, datetime) else dt
    return d in _holiday_set()


def is_trading_day(dt: datetime | date | None = None) -> bool:
    if dt is None:
        dt = now_ist()
    d = dt.date() if isinstance(dt, datetime) else dt
    if d.weekday() >= 5:
        return False
    return not is_nse_holiday(d)


def session_kind(dt: datetime | None = None) -> str:
    """weekend | holiday | closed | preopen | regular | closing | after_hours"""
    dt = dt or now_ist()
    if dt.weekday() >= 5:
        return "weekend"
    if is_nse_holiday(dt):
        return "holiday"
    t = dt.time()
    if PREOPEN <= t < OPEN:
        return "preopen"
    if OPEN <= t <= CLOSE:
        return "regular"
    if CLOSING_SESSION_OPEN <= t <= CLOSING_SESSION_CLOSE:
        return "closing"
    if t < PREOPEN:
        return "closed"
    return "after_hours"


def is_market_open(dt: datetime | None = None) -> bool:
    return session_kind(dt) == "regular"


def ticks_expected(dt: datetime | None = None) -> bool:
    return session_kind(dt) == "regular"


def session_phase(dt: datetime | None = None) -> str:
    """Runner phase name used by the always-on collector."""
    dt = dt or now_ist()
    if not is_trading_day(dt):
        return "idle"
    t = dt.time()
    if t < INIT:
        return "idle"
    if t < KITE_AUTH:
        return "init"
    if t < SYNC_INSTRUMENTS:
        return "kite_auth"
    if t < PREMARKET:
        return "sync_instruments"
    if t < COLLECT_START:
        return "premarket"
    if t <= COLLECT_STOP:
        return "collect"
    if t < FINALIZE:
        return "stopping"
    if t < DAILY_REPORT:
        return "finalize"
    if t < ARCHIVE:
        return "report"
    return "archive"


def session_state(dt: datetime | None = None) -> dict:
    dt = dt or now_ist()
    kind = session_kind(dt)
    return {
        "open": kind == "regular",
        "kind": kind,
        "phase": session_phase(dt),
        "ticks_expected": kind == "regular",
        "trading_day": is_trading_day(dt),
        "holiday": is_nse_holiday(dt),
        "now_ist": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": dt.strftime("%A"),
        "session": f"{OPEN.strftime('%H:%M')}-{CLOSE.strftime('%H:%M')} IST",
    }
