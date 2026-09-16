"""Deterministic replay tape for tests and local demo when Kite is unavailable."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from backend.market import IST, OPEN


def session_tape(session_date: str, bars: int = 120, start_spot: float = 24850.0) -> list[dict]:
    """One-minute bars from 09:15 IST. Seeded by session_date — not random live noise."""
    seed = int(session_date.replace("-", "") or "20260101")
    rng = random.Random(seed)
    d = datetime.fromisoformat(session_date).replace(tzinfo=IST)
    t0 = d.replace(hour=OPEN.hour, minute=OPEN.minute, second=0, microsecond=0)
    px = start_spot
    out = []
    for i in range(bars):
        drift = 0.35 * math.sin(i / 18) + 0.15 * math.sin(i / 7)
        shock = rng.gauss(0, 3.2)
        o = px
        c = max(100.0, px + drift + shock)
        h = max(o, c) + abs(rng.gauss(0, 2.2))
        l = min(o, c) - abs(rng.gauss(0, 2.2))
        vol = int(abs(rng.gauss(12_000, 3_000)))
        ts = t0 + timedelta(minutes=i)
        bid = c - 0.35
        ask = c + 0.35
        qty = abs(int(rng.gauss(800, 200)))
        out.append({
            "ts": ts.isoformat(),
            "time": int(ts.timestamp()),
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": vol,
            "ltp": round(c, 2),
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "qty": qty,
        })
        px = c
    return out
