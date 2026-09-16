"""News ingest with recency decay so old headlines cannot dominate signals."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

SOURCES = [
    ("https://www.nseindia.com/api/latest-announcements", "NSE"),
]


SEED_ITEMS = [
    {
        "source": "NSE",
        "headline": "Nifty 50 index constituents — session watch",
        "sentiment": "NEUTRAL",
        "relevance": 0.6,
        "impact": "low",
        "confidence": 0.4,
    },
    {
        "source": "RBI",
        "headline": "No unscheduled monetary policy announcement in the current window",
        "sentiment": "NEUTRAL",
        "relevance": 0.5,
        "impact": "low",
        "confidence": 0.5,
    },
]


def recency_weight(ts: float, now: float | None = None, half_life_min: float = 90.0) -> float:
    if now is None:
        now = time.time()
    age_min = max(0.0, (now - ts) / 60.0)
    return 0.5 ** (age_min / half_life_min)


def enrich(item: dict, ts: float | None = None) -> dict:
    ts = ts or time.time()
    w = recency_weight(ts)
    out = dict(item)
    out["timestamp"] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    out["ts"] = ts
    out["recency_weight"] = round(w, 3)
    out["effective_relevance"] = round(float(item.get("relevance") or 0) * w, 3)
    return out


def collect_news(enabled: bool = True) -> list[dict]:
    now = time.time()
    items = [enrich(dict(x), now) for x in SEED_ITEMS]
    if not enabled:
        return items
    try:
        import feedparser  # type: ignore
        feeds = [
            ("https://www.moneycontrol.com/rss/latestnews.xml", "Moneycontrol"),
            ("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC Business"),
        ]
        for url, source in feeds:
            parsed = feedparser.parse(url)
            for e in list(parsed.entries)[:5]:
                title = str(getattr(e, "title", "") or "")
                if not title:
                    continue
                items.append(enrich({
                    "source": source,
                    "headline": title[:240],
                    "sentiment": _sentiment(title),
                    "relevance": 0.45,
                    "impact": "medium" if any(k in title.lower() for k in ("fed", "rbi", "crude", "inr", "fii")) else "low",
                    "confidence": 0.4,
                }, now))
    except Exception:
        pass
    items.sort(key=lambda x: x.get("effective_relevance", 0), reverse=True)
    return items[:30]


def _sentiment(title: str) -> str:
    t = title.lower()
    bull = ("rally", "surge", "gain", "cut rates", "peace", "beat")
    bear = ("crash", "fall", "war", "hike", "default", "miss", "sanctions")
    if any(w in t for w in bull):
        return "BULLISH"
    if any(w in t for w in bear):
        return "BEARISH"
    return "NEUTRAL"


def news_bias(items: list[dict]) -> dict:
    if not items:
        return {"bias": "NEUTRAL", "confidence": 0.0, "dominant_age": None}
    score = 0.0
    weight = 0.0
    for it in items:
        w = float(it.get("effective_relevance") or 0)
        if it.get("sentiment") == "BULLISH":
            score += w
        elif it.get("sentiment") == "BEARISH":
            score -= w
        weight += w
    if weight < 0.15:
        return {"bias": "NEUTRAL", "confidence": 0.1, "note": "stale or low-relevance news discounted"}
    if score > 0.15:
        bias = "BULLISH"
    elif score < -0.15:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    return {"bias": bias, "confidence": round(min(1.0, abs(score)), 2)}
