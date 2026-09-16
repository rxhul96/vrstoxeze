"""Paper signal tracking from subsequent candles. Never talks to Kite orders."""
from __future__ import annotations


def grade(signal: dict, later_closes: list[float]) -> dict:
    if not later_closes or signal.get("direction") in (None, "NO SIGNAL"):
        return {"outcome": "unscored", "move_pts": 0.0}
    start = later_closes[0]
    end = later_closes[-1]
    move = end - start
    direction = signal.get("direction")
    t1 = signal.get("target_1")
    inv = signal.get("invalidation")
    hit_t1 = False
    stopped = False
    for px in later_closes:
        if direction == "BULLISH":
            if t1 is not None and px >= t1:
                hit_t1 = True
            if inv is not None and px <= inv:
                stopped = True
                break
        elif direction == "BEARISH":
            if t1 is not None and px <= t1:
                hit_t1 = True
            if inv is not None and px >= inv:
                stopped = True
                break
    if stopped and not hit_t1:
        outcome = "false"
    elif hit_t1:
        outcome = "true"
    else:
        outcome = "open"
    return {
        "outcome": outcome,
        "move_pts": round(move, 2),
        "broker": None,
        "note": "Paper tracking uses candles only — no broker interaction.",
    }
