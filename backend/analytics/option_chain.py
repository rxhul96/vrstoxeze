"""NIFTY option-chain constructor (CE left, strike center, PE right)."""
from __future__ import annotations

import random


def build_chain(spot: float, step: int = 50, depth: int = 12, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random(int(spot))
    atm = int(round(spot / step) * step)
    rows = []
    for i in range(-depth, depth + 1):
        strike = atm + i * step
        moneyness = (strike - spot) / max(spot, 1)
        ce_oi = max(40_000, int(180_000 * (1.2 - abs(min(moneyness, 0)) * 8) + rng.randint(-8000, 8000)))
        pe_oi = max(40_000, int(180_000 * (1.2 - abs(max(moneyness, 0)) * 8) + rng.randint(-8000, 8000)))
        ce_doi = int(rng.randint(-12_000, 18_000) - i * 400)
        pe_doi = int(rng.randint(-12_000, 18_000) + i * 400)
        ce_ltp = max(1.0, 180 - abs(i) * 11 + rng.random() * 4)
        pe_ltp = max(1.0, 175 - abs(i) * 11 + rng.random() * 4)
        rows.append({
            "strike": strike,
            "atm": strike == atm,
            "ce": {
                "ltp": round(ce_ltp, 2),
                "dltp": round(rng.uniform(-4, 4), 2),
                "oi": ce_oi,
                "doi": ce_doi,
                "vol": int(abs(ce_doi) * 1.4 + rng.randint(500, 4000)),
                "iv": round(12 + abs(i) * 0.35, 1),
            },
            "pe": {
                "ltp": round(pe_ltp, 2),
                "dltp": round(rng.uniform(-4, 4), 2),
                "oi": pe_oi,
                "doi": pe_doi,
                "vol": int(abs(pe_doi) * 1.4 + rng.randint(500, 4000)),
                "iv": round(12.5 + abs(i) * 0.35, 1),
            },
        })
    return {"spot": spot, "atm": atm, "step": step, "depth": depth, "rows": rows}
