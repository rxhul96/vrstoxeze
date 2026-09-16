"""Specialist analysts consume structured evidence — never ticks, never Kite."""
from __future__ import annotations

from typing import Callable

# Agents are not given any broker or execution callable.
FORBIDDEN_TOOLS = ("place_order", "modify_order", "cancel_order", "execute_order")


def _view(evidence: dict, *keys: str) -> dict:
    return {k: evidence.get(k) for k in keys}


def market_agent(evidence: dict) -> dict:
    pa = evidence.get("price_action") or {}
    return {"name": "MarketAgent", "bias": pa.get("bias") or "NEUTRAL", "note": pa.get("structure") or "n/a"}


def options_agent(evidence: dict) -> dict:
    oi = evidence.get("option_flow") or {}
    return {"name": "OptionsAgent", "bias": oi.get("bias") or "NEUTRAL", "note": (oi.get("call") or {}).get("evidence")}


def cvd_volume_agent(evidence: dict) -> dict:
    cvd = evidence.get("cvd") or {}
    vol = evidence.get("volume") or {}
    return {
        "name": "CVDVolumeAgent",
        "bias": cvd.get("bias") or "NEUTRAL",
        "note": f"{cvd.get('methodology')} / rvol={vol.get('rvol')}",
    }


def technical_agent(evidence: dict) -> dict:
    pa = evidence.get("price_action") or {}
    return {"name": "TechnicalAgent", "bias": pa.get("bias") or "NEUTRAL", "note": pa.get("event") or pa.get("structure")}


def ict_agent(evidence: dict) -> dict:
    ict = evidence.get("ict") or {}
    return {"name": "ICTAgent", "bias": ict.get("bias") or "NEUTRAL", "note": f"{len(ict.get('events') or [])} events"}


def news_agent(evidence: dict) -> dict:
    news = evidence.get("news") or {}
    return {"name": "NewsAgent", "bias": news.get("bias") or "NEUTRAL", "note": "recency-decayed"}


def sentiment_agent(evidence: dict) -> dict:
    news = evidence.get("news") or {}
    return {"name": "SentimentAgent", "bias": news.get("bias") or "NEUTRAL", "note": news}


def regime_agent(evidence: dict) -> dict:
    rg = evidence.get("regime") or {}
    return {"name": "RegimeAgent", "bias": rg.get("bias") or "NEUTRAL", "note": rg.get("regime")}


SPECIALISTS: list[Callable[[dict], dict]] = [
    market_agent,
    options_agent,
    cvd_volume_agent,
    technical_agent,
    ict_agent,
    news_agent,
    sentiment_agent,
    regime_agent,
]


def run_desk(evidence: dict) -> list[dict]:
    return [fn(evidence) for fn in SPECIALISTS]


def master_analyst(evidence: dict, score: dict, specialists: list[dict]) -> dict:
    """Synthesize. Identify conflicts. No execution tools."""
    biases = [s["bias"] for s in specialists if s.get("bias") and s["bias"] != "NEUTRAL"]
    unique = set(biases)
    conflicts = []
    if "BULLISH" in unique and "BEARISH" in unique:
        conflicts = [s["name"] for s in specialists if s.get("bias") in ("BULLISH", "BEARISH")]
    master_bias = score.get("bias") or "NEUTRAL"
    if score.get("mixed") or conflicts and abs(score.get("raw") or 0) < 18:
        master_bias = "NEUTRAL"
        headline = "NO HIGH-CONFIDENCE SIGNAL"
    else:
        headline = f"MASTER BIAS: {master_bias}"
    narrative = "; ".join(f"{s['name']}={s['bias']}" for s in specialists)
    return {
        "name": "MasterAnalystAgent",
        "bias": master_bias,
        "headline": headline,
        "conflicts": conflicts,
        "specialists": specialists,
        "narrative": narrative,
        "tools": [],
        "execution": False,
    }
