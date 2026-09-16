"""Tick-level cumulative volume delta. Always labeled ESTIMATED CVD."""
from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Optional

from .lee_ready import classify_print

GENUINE_BUYING = "genuine_buying"
BEARISH_DIVERGENCE = "bearish_divergence"
GENUINE_SELLING = "genuine_selling"
BULLISH_DIVERGENCE = "bullish_divergence"
FLAT = "flat"


class CvdEngine:
    """Session CVD accumulator. Methodology is always estimated (no aggressor flag)."""

    methodology = "ESTIMATED CVD"
    methodology_note = (
        "Kite does not provide true aggressor-side prints. "
        "CVD is estimated via Lee-Ready (quote/tick rule)."
    )

    def __init__(self) -> None:
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.cumulative_delta = 0.0
        self._history: deque[tuple[float, float, float]] = deque(maxlen=600)
        self._last_price: Optional[float] = None
        self._last_cvd: Optional[float] = None
        self.session_date: Optional[str] = None

    def reset_session(self, session_date: str) -> None:
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.cumulative_delta = 0.0
        self._history.clear()
        self.session_date = session_date

    def ingest(
        self,
        price: float,
        qty: float,
        bid: float | None = None,
        ask: float | None = None,
        ts: float | None = None,
    ) -> dict:
        side = classify_print(price, self._last_price, bid, ask)
        if side == "buy":
            self.buy_volume += qty
            self.cumulative_delta += qty
        elif side == "sell":
            self.sell_volume += qty
            self.cumulative_delta -= qty
        now = ts or datetime.utcnow().timestamp()
        self._history.append((now, price, self.cumulative_delta))
        self._last_price = price
        snap = self.snapshot(price)
        self._last_cvd = self.cumulative_delta
        return snap

    def _slope(self) -> float | None:
        if len(self._history) < 8:
            return None
        a = self._history[0]
        b = self._history[-1]
        dt = b[0] - a[0]
        if dt <= 0:
            return None
        return (b[2] - a[2]) / dt

    def _acceleration(self) -> float | None:
        if len(self._history) < 16:
            return None
        mid = len(self._history) // 2
        first = list(self._history)[:mid]
        second = list(self._history)[mid:]
        def sl(win):
            dt = win[-1][0] - win[0][0]
            if dt <= 0:
                return 0.0
            return (win[-1][2] - win[0][2]) / dt
        return sl(second) - sl(first)

    def snapshot(self, price: float | None = None) -> dict:
        slope = self._slope()
        acc = self._acceleration()
        label = FLAT
        px = price if price is not None else (self._last_price or 0)
        if len(self._history) >= 8:
            p0, c0 = self._history[0][1], self._history[0][2]
            p1, c1 = self._history[-1][1], self._history[-1][2]
            up_p, up_c = p1 > p0, c1 > c0
            dn_p, dn_c = p1 < p0, c1 < c0
            if up_p and up_c:
                label = GENUINE_BUYING
            elif up_p and dn_c:
                label = BEARISH_DIVERGENCE
            elif dn_p and dn_c:
                label = GENUINE_SELLING
            elif dn_p and up_c:
                label = BULLISH_DIVERGENCE
        event = None
        if slope is not None:
            if slope > 40:
                event = "cvd_breakout"
            elif slope < -40:
                event = "cvd_breakdown"
        bias = "NEUTRAL"
        if label in (GENUINE_BUYING, BULLISH_DIVERGENCE):
            bias = "BULLISH"
        elif label in (GENUINE_SELLING, BEARISH_DIVERGENCE):
            bias = "BEARISH"
        return {
            "methodology": self.methodology,
            "methodology_note": self.methodology_note,
            "buy_volume": round(self.buy_volume, 2),
            "sell_volume": round(self.sell_volume, 2),
            "delta": round(self.buy_volume - self.sell_volume, 2),
            "cumulative_delta": round(self.cumulative_delta, 2),
            "slope": None if slope is None else round(slope, 4),
            "acceleration": None if acc is None else round(acc, 4),
            "label": label,
            "bias": bias,
            "event": event,
            "price": px,
        }
