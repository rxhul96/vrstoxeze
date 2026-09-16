"""Volume + a thin technical set. Avoid indicator overload."""
from __future__ import annotations

from collections import deque
import math


class VolumeTaEngine:
    def __init__(self) -> None:
        self.candles: deque[dict] = deque(maxlen=400)
        self.cum_pv = 0.0
        self.cum_vol = 0.0

    def push(self, candle: dict) -> dict:
        self.candles.append(candle)
        vol = float(candle.get("volume") or 0)
        close = float(candle["close"])
        self.cum_pv += close * vol
        self.cum_vol += vol
        return self.snapshot()

    def _ema(self, period: int) -> float | None:
        if len(self.candles) < period:
            return None
        k = 2 / (period + 1)
        ema = float(self.candles[0]["close"])
        for c in list(self.candles)[1:]:
            ema = float(c["close"]) * k + ema * (1 - k)
        return ema

    def _rsi(self, period: int = 14) -> float | None:
        if len(self.candles) < period + 1:
            return None
        gains, losses = 0.0, 0.0
        arr = list(self.candles)[-(period + 1):]
        for i in range(1, len(arr)):
            d = arr[i]["close"] - arr[i - 1]["close"]
            if d >= 0:
                gains += d
            else:
                losses -= d
        if losses == 0:
            return 100.0
        rs = (gains / period) / (losses / period)
        return 100 - (100 / (1 + rs))

    def _atr(self, period: int = 14) -> float | None:
        if len(self.candles) < period + 1:
            return None
        trs = []
        arr = list(self.candles)
        for i in range(1, len(arr)):
            h, l, pc = arr[i]["high"], arr[i]["low"], arr[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs[-period:]) / period

    def snapshot(self) -> dict:
        if not self.candles:
            return {"bias": "NEUTRAL"}
        last = self.candles[-1]
        vols = [float(c.get("volume") or 0) for c in self.candles]
        avg = sum(vols[:-1]) / max(len(vols) - 1, 1)
        rvol = (vols[-1] / avg) if avg else 1.0
        vwap = (self.cum_pv / self.cum_vol) if self.cum_vol else last["close"]
        ema20 = self._ema(20)
        ema50 = self._ema(50)
        rsi = self._rsi()
        atr = self._atr()
        close = last["close"]
        spike = rvol >= 2.0
        accel = 0.0
        if len(vols) >= 6:
            accel = sum(vols[-3:]) / 3 - sum(vols[-6:-3]) / 3
        structure = "range"
        if ema20 and ema50:
            if close > ema20 > ema50:
                structure = "uptrend"
            elif close < ema20 < ema50:
                structure = "downtrend"
        event = None
        if len(self.candles) >= 20:
            hi = max(c["high"] for c in list(self.candles)[-20:-1])
            lo = min(c["low"] for c in list(self.candles)[-20:-1])
            if close > hi:
                event = "breakout"
            elif close < lo:
                event = "breakdown"
        bias = "NEUTRAL"
        if structure == "uptrend" and close > vwap:
            bias = "BULLISH"
        elif structure == "downtrend" and close < vwap:
            bias = "BEARISH"
        return {
            "rvol": round(rvol, 2),
            "volume_spike": spike,
            "volume_acceleration": round(accel, 1),
            "vwap": round(vwap, 2),
            "ema20": None if ema20 is None else round(ema20, 2),
            "ema50": None if ema50 is None else round(ema50, 2),
            "rsi": None if rsi is None else round(rsi, 1),
            "atr": None if atr is None else round(atr, 2),
            "structure": structure,
            "event": event,
            "bias": bias,
            "close": close,
        }
