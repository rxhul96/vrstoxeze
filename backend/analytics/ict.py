"""ICT / liquidity labels inferred only from OHLC candles."""
from __future__ import annotations


def analyze(candles: list[dict]) -> dict:
    if len(candles) < 10:
        return {"bias": "NEUTRAL", "events": [], "note": "insufficient candles"}
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    session_high = max(highs)
    session_low = min(lows)
    pdh = max(highs[: max(1, len(highs) // 4)])
    pdl = min(lows[: max(1, len(lows) // 4)])
    events: list[dict] = []
    last = candles[-1]

    def eq_level(values: list[float], tol: float) -> list[float]:
        found = []
        for i, a in enumerate(values):
            for b in values[i + 1:]:
                if abs(a - b) <= tol and a not in found:
                    found.append(a)
        return found[:4]

    atr = (session_high - session_low) / max(len(candles), 1)
    eq_h = eq_level(highs[-40:], atr * 0.15)
    eq_l = eq_level(lows[-40:], atr * 0.15)
    if eq_h:
        events.append({"type": "equal_highs", "level": eq_h[0]})
    if eq_l:
        events.append({"type": "equal_lows", "level": eq_l[0]})

    if last["high"] > session_high * 0.999 and last["close"] < last["high"] - atr:
        events.append({"type": "liquidity_sweep", "side": "highs", "level": last["high"]})
    if last["low"] < session_low * 1.001 and last["close"] > last["low"] + atr:
        events.append({"type": "liquidity_sweep", "side": "lows", "level": last["low"]})

    # Fair value gap: 3-candle imbalance
    if len(candles) >= 3:
        a, b, c = candles[-3], candles[-2], candles[-1]
        if a["high"] < c["low"]:
            events.append({"type": "fvg", "side": "bullish", "low": a["high"], "high": c["low"]})
        if a["low"] > c["high"]:
            events.append({"type": "fvg", "side": "bearish", "low": c["high"], "high": a["low"]})

    mid = (session_high + session_low) / 2
    premium = last["close"] > mid
    bos = None
    if last["close"] > max(highs[-10:-1], default=last["close"]):
        bos = "BOS_UP"
        events.append({"type": "bos", "side": "up"})
    elif last["close"] < min(lows[-10:-1], default=last["close"]):
        bos = "BOS_DOWN"
        events.append({"type": "bos", "side": "down"})

    bias = "NEUTRAL"
    if bos == "BOS_UP" or (not premium and any(e["type"] == "fvg" and e.get("side") == "bullish" for e in events)):
        bias = "BULLISH"
    elif bos == "BOS_DOWN" or (premium and any(e["type"] == "fvg" and e.get("side") == "bearish" for e in events)):
        bias = "BEARISH"

    return {
        "session_high": session_high,
        "session_low": session_low,
        "prev_day_high": pdh,
        "prev_day_low": pdl,
        "premium": premium,
        "discount": not premium,
        "events": events,
        "bias": bias,
        "note": "ICT labels are inferred from OHLC only; no order-book liquidity map is claimed.",
    }
