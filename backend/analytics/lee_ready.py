"""Lee-Ready tick rule. Kite does not provide aggressor flags — this is ESTIMATED."""
from __future__ import annotations


def classify_print(
    price: float,
    prev_price: float | None,
    bid: float | None = None,
    ask: float | None = None,
) -> str:
    """Return buy | sell | unknown. Quote rule first, then tick rule."""
    if bid is not None and ask is not None and ask > bid:
        mid = (bid + ask) / 2.0
        if price > mid:
            return "buy"
        if price < mid:
            return "sell"
    if prev_price is None:
        return "unknown"
    if price > prev_price:
        return "buy"
    if price < prev_price:
        return "sell"
    return "unknown"
