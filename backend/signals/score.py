"""Frozen institutional market score. AI cannot change these weights."""
from __future__ import annotations

WEIGHTS = {
    "cvd": 20,
    "option_flow": 20,
    "price_action": 20,
    "volume": 10,
    "pcr": 10,
    "ict": 10,
    "news": 5,
    "regime": 5,
}

assert sum(WEIGHTS.values()) == 100, "weights must sum to 100"

BIAS_SCORE = {"BULLISH": 1.0, "BEARISH": -1.0, "NEUTRAL": 0.0}


def _leg(key: str, bias: str, confidence: float = 0.6) -> dict:
    signed = BIAS_SCORE.get(bias, 0.0) * max(0.0, min(1.0, confidence))
    points = WEIGHTS[key] * signed
    return {
        "key": key,
        "weight": WEIGHTS[key],
        "bias": bias,
        "confidence": round(confidence, 2),
        "contribution": round(points, 2),
    }


def compute(evidence: dict) -> dict:
    """evidence values are {bias, confidence} per factor."""
    parts = []
    mapping = {
        "cvd": evidence.get("cvd") or {},
        "option_flow": evidence.get("option_flow") or {},
        "price_action": evidence.get("price_action") or {},
        "volume": evidence.get("volume") or {},
        "pcr": evidence.get("pcr") or {},
        "ict": evidence.get("ict") or {},
        "news": evidence.get("news") or {},
        "regime": evidence.get("regime") or {},
    }
    # PCR is context: force NEUTRAL contribution unless strongly aligned and not used alone.
    pcr = mapping["pcr"]
    mapping["pcr"] = {
        "bias": "NEUTRAL" if pcr.get("bias") in (None, "NEUTRAL") else pcr.get("bias", "NEUTRAL"),
        "confidence": min(float(pcr.get("confidence") or 0.3), 0.5),
    }
    for key, val in mapping.items():
        parts.append(_leg(key, val.get("bias") or "NEUTRAL", float(val.get("confidence") or 0.5)))
    total = sum(p["contribution"] for p in parts)
    # Map -100..100 to 0..100 display score centered at 50.
    display = round(50 + total / 2, 1)
    if total >= 18:
        bias = "BULLISH"
    elif total <= -18:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    conflicts = [
        p["key"] for p in parts
        if p["bias"] not in (bias, "NEUTRAL") and bias != "NEUTRAL"
    ]
    mixed = len({p["bias"] for p in parts if p["bias"] != "NEUTRAL"}) > 1 and abs(total) < 18
    return {
        "weights": dict(WEIGHTS),
        "parts": parts,
        "raw": round(total, 2),
        "score": display,
        "bias": bias,
        "conflicts": conflicts,
        "mixed": mixed,
        "weights_locked": True,
    }
