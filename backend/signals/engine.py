"""Signal engine — analytical states only. Never calls a broker."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.signals.score import compute as compute_score

DIRECTIONS = ("BULLISH", "BEARISH", "CALL BUY BIAS", "PUT BUY BIAS", "NO SIGNAL")
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


def build_signal(evidence: dict, spot: float, atr: float | None, score: dict | None = None) -> dict:
    score = score or compute_score(evidence)
    conflicts = list(score.get("conflicts") or [])
    mixed = bool(score.get("mixed"))
    reasons = []
    for p in score["parts"]:
        if p["bias"] != "NEUTRAL":
            reasons.append(f"{p['key']}: {p['bias']} ({p['contribution']:+.1f})")

    if mixed or score["bias"] == "NEUTRAL" or abs(score["raw"]) < 18:
        return {
            "signal_id": None,
            "direction": "NO SIGNAL",
            "instrument_type": "NIFTY",
            "signal_type": "NO HIGH-CONFIDENCE SIGNAL",
            "confidence": round(min(0.49, abs(score["raw"]) / 50), 2),
            "score": score["score"],
            "score_breakdown": score["parts"],
            "entry_zone": None,
            "target_1": None,
            "target_2": None,
            "invalidation": None,
            "risk_reward": None,
            "timeframe": "intraday",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "expiry": None,
            "reasons": reasons or ["evidence mixed or insufficient"],
            "conflicts": conflicts or [p["key"] for p in score["parts"] if p["bias"] != "NEUTRAL"],
            "state": "WATCHING",
            "execution": "SIGNAL-ONLY — no broker action",
        }

    atr = atr or max(spot * 0.0025, 20)
    if score["bias"] == "BULLISH":
        direction = "BULLISH"
        signal_type = "CALL BUY BIAS"
        entry = (round(spot - atr * 0.2, 1), round(spot + atr * 0.15, 1))
        t1 = round(spot + atr * 1.0, 1)
        t2 = round(spot + atr * 1.8, 1)
        inv = round(spot - atr * 1.1, 1)
        rr = round((t1 - spot) / max(spot - inv, 1), 2)
    else:
        direction = "BEARISH"
        signal_type = "PUT BUY BIAS"
        entry = (round(spot - atr * 0.15, 1), round(spot + atr * 0.2, 1))
        t1 = round(spot - atr * 1.0, 1)
        t2 = round(spot - atr * 1.8, 1)
        inv = round(spot + atr * 1.1, 1)
        rr = round((spot - t1) / max(inv - spot, 1), 2)

    confidence = min(0.92, 0.55 + abs(score["raw"]) / 200)
    return {
        "signal_id": str(uuid.uuid4()),
        "direction": direction,
        "instrument_type": "NIFTY",
        "signal_type": signal_type,
        "confidence": round(confidence, 2),
        "score": score["score"],
        "score_breakdown": score["parts"],
        "entry_zone": {"low": min(entry), "high": max(entry)},
        "target_1": t1,
        "target_2": t2,
        "invalidation": inv,
        "risk_reward": rr,
        "timeframe": "intraday",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "expiry": "current week",
        "reasons": reasons,
        "conflicts": conflicts,
        "state": "TRIGGERED",
        "execution": "SIGNAL-ONLY — no broker action",
    }
