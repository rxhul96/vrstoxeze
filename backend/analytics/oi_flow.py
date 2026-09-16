"""Option flow classification from OI change + price change + volume."""
from __future__ import annotations


def classify_leg(oi_chg: float, price_chg: float, volume: float) -> dict:
    """Return interpretation for one CE or PE leg."""
    if volume <= 0 or (oi_chg == 0 and price_chg == 0):
        return {
            "label": "quiet",
            "bias": "NEUTRAL",
            "confidence": 0.15,
            "evidence": "no meaningful OI or price change",
        }
    strength = min(1.0, (abs(oi_chg) / max(1.0, abs(oi_chg) + 1)) * 0.6 + min(volume / 50_000, 1) * 0.4)
    if oi_chg > 0 and price_chg < 0:
        return {
            "label": "writing",
            "bias": "BEARISH" if True else "NEUTRAL",
            "confidence": round(0.45 + 0.4 * strength, 2),
            "evidence": "OI up + price down → possible writing",
        }
    if oi_chg > 0 and price_chg > 0:
        return {
            "label": "buying",
            "bias": "BULLISH",
            "confidence": round(0.45 + 0.4 * strength, 2),
            "evidence": "OI up + price up → possible buying",
        }
    if oi_chg < 0 and price_chg > 0:
        return {
            "label": "short_covering",
            "bias": "BULLISH",
            "confidence": round(0.4 + 0.35 * strength, 2),
            "evidence": "OI down + price up → possible short covering",
        }
    if oi_chg < 0 and price_chg < 0:
        return {
            "label": "long_unwinding",
            "bias": "BEARISH",
            "confidence": round(0.4 + 0.35 * strength, 2),
            "evidence": "OI down + price down → possible long unwinding",
        }
    return {
        "label": "mixed",
        "bias": "NEUTRAL",
        "confidence": 0.25,
        "evidence": "OI/price signs do not form a clean pattern",
    }


def classify_chain(rows: list[dict], atm: float) -> dict:
    """Aggregate ATM ±2 flow. Call writing is bearish; put writing is bullish."""
    nearby = [r for r in rows if abs(r["strike"] - atm) <= (rows[1]["strike"] - rows[0]["strike"]) * 2] if len(rows) > 1 else rows
    ce_oi = sum(r["ce"]["doi"] for r in nearby)
    pe_oi = sum(r["pe"]["doi"] for r in nearby)
    ce_px = sum(r["ce"]["dltp"] for r in nearby)
    pe_px = sum(r["pe"]["dltp"] for r in nearby)
    ce_vol = sum(r["ce"]["vol"] for r in nearby)
    pe_vol = sum(r["pe"]["vol"] for r in nearby)
    ce = classify_leg(ce_oi, ce_px, ce_vol)
    pe = classify_leg(pe_oi, pe_px, pe_vol)
    if ce["label"] == "writing":
        ce["bias"] = "BEARISH"
    if pe["label"] == "writing":
        pe["bias"] = "BULLISH"
    if ce["label"] == "buying":
        ce["bias"] = "BULLISH"
    if pe["label"] == "buying":
        pe["bias"] = "BEARISH"
    scores = {"BULLISH": 0.0, "BEARISH": 0.0, "NEUTRAL": 0.0}
    scores[ce["bias"]] += ce["confidence"]
    scores[pe["bias"]] += pe["confidence"]
    bias = max(scores, key=scores.get)
    return {
        "call": ce,
        "put": pe,
        "bias": bias,
        "confidence": round(max(scores.values()) / 2, 2),
        "atm": atm,
        "ce_doi": ce_oi,
        "pe_doi": pe_oi,
    }


def heatmap(rows: list[dict]) -> list[dict]:
    """Normalize ΔOI for bars — intensity is |ΔOI| / max|ΔOI|, not total OI."""
    max_abs = max((abs(r["ce"]["doi"]) for r in rows), default=1) or 1
    max_abs_pe = max((abs(r["pe"]["doi"]) for r in rows), default=1) or 1
    peak = max(max_abs, max_abs_pe, 1)
    out = []
    for r in rows:
        ce_n = r["ce"]["doi"] / peak
        pe_n = r["pe"]["doi"] / peak
        out.append({
            "strike": r["strike"],
            "ce_oi": r["ce"]["oi"],
            "pe_oi": r["pe"]["oi"],
            "ce_doi": r["ce"]["doi"],
            "pe_doi": r["pe"]["doi"],
            "ce_intensity": round(ce_n, 3),
            "pe_intensity": round(pe_n, 3),
            "ce_kind": "buildup" if r["ce"]["doi"] > 0 else ("unwind" if r["ce"]["doi"] < 0 else "flat"),
            "pe_kind": "buildup" if r["pe"]["doi"] > 0 else ("unwind" if r["pe"]["doi"] < 0 else "flat"),
        })
    if rows:
        max_ce = max(rows, key=lambda r: r["ce"]["oi"])
        max_pe = max(rows, key=lambda r: r["pe"]["oi"])
        for item in out:
            item["resistance"] = item["strike"] == max_ce["strike"]
            item["support"] = item["strike"] == max_pe["strike"]
    return out
