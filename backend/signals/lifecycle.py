"""Analytical signal lifecycle. States never trigger broker actions."""
from __future__ import annotations

STATES = (
    "WATCHING",
    "TRIGGERED",
    "ACTIVE",
    "CONFIRMED",
    "WEAKENING",
    "INVALIDATED",
    "TARGET 1 REACHED",
    "TARGET 2 REACHED",
    "EXPIRED",
)


def next_state(signal: dict, spot: float) -> str:
    state = signal.get("state") or "WATCHING"
    direction = signal.get("direction")
    if direction in (None, "NO SIGNAL"):
        return "WATCHING"
    inv = signal.get("invalidation")
    t1 = signal.get("target_1")
    t2 = signal.get("target_2")
    entry = signal.get("entry_zone") or {}
    lo, hi = entry.get("low"), entry.get("high")
    if direction == "BULLISH":
        if inv is not None and spot <= inv:
            return "INVALIDATED"
        if t2 is not None and spot >= t2:
            return "TARGET 2 REACHED"
        if t1 is not None and spot >= t1:
            return "TARGET 1 REACHED"
        if lo is not None and hi is not None and lo <= spot <= hi:
            return "ACTIVE" if state == "TRIGGERED" else "CONFIRMED"
        if t1 is not None and spot > (lo or spot) and spot < t1:
            return "WEAKENING" if state == "CONFIRMED" and spot < (lo or spot) else state
    if direction == "BEARISH":
        if inv is not None and spot >= inv:
            return "INVALIDATED"
        if t2 is not None and spot <= t2:
            return "TARGET 2 REACHED"
        if t1 is not None and spot <= t1:
            return "TARGET 1 REACHED"
        if lo is not None and hi is not None and lo <= spot <= hi:
            return "ACTIVE" if state == "TRIGGERED" else "CONFIRMED"
    return state
