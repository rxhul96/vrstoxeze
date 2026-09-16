"""Market regime classification from structure + ATR + CVD + volume + OI."""
from __future__ import annotations

REGIMES = (
    "Trending Bullish",
    "Trending Bearish",
    "Range",
    "Breakout",
    "Breakdown",
    "High Volatility",
    "Low Volatility",
    "Uncertain",
)


def classify(ta: dict, cvd: dict, oi: dict | None = None) -> dict:
    structure = ta.get("structure") or "range"
    event = ta.get("event")
    atr = ta.get("atr") or 0
    close = ta.get("close") or 0
    rvol = ta.get("rvol") or 1
    cvd_bias = cvd.get("bias") or "NEUTRAL"
    vol_ratio = (atr / close * 10_000) if close else 0  # bps
    high_vol = vol_ratio > 25 or rvol > 2.2
    low_vol = vol_ratio < 8 and rvol < 0.8

    regime = "Uncertain"
    if event == "breakout":
        regime = "Breakout"
    elif event == "breakdown":
        regime = "Breakdown"
    elif structure == "uptrend" and cvd_bias == "BULLISH":
        regime = "Trending Bullish"
    elif structure == "downtrend" and cvd_bias == "BEARISH":
        regime = "Trending Bearish"
    elif structure == "range":
        regime = "Range"
    if high_vol and regime in ("Range", "Uncertain"):
        regime = "High Volatility"
    if low_vol and regime == "Range":
        regime = "Low Volatility"

    bias = "NEUTRAL"
    if regime in ("Trending Bullish", "Breakout"):
        bias = "BULLISH"
    elif regime in ("Trending Bearish", "Breakdown"):
        bias = "BEARISH"
    return {
        "regime": regime,
        "bias": bias,
        "high_volatility": high_vol,
        "low_volatility": low_vol,
        "atr_bps": round(vol_ratio, 1),
        "allowed": list(REGIMES),
    }
