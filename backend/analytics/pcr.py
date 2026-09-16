"""PCR analytics. PCR never independently generates a trade signal."""
from __future__ import annotations

from collections import deque


class PcrEngine:
    def __init__(self) -> None:
        self._hist: deque[tuple[float, float]] = deque(maxlen=240)

    def compute(self, rows: list[dict], atm: float, step: float, ts: float) -> dict:
        ce_oi = sum(r["ce"]["oi"] for r in rows) or 1
        pe_oi = sum(r["pe"]["oi"] for r in rows)
        ce_vol = sum(r["ce"]["vol"] for r in rows) or 1
        pe_vol = sum(r["pe"]["vol"] for r in rows)
        oi_pcr = pe_oi / ce_oi
        vol_pcr = pe_vol / ce_vol
        nearby = [r for r in rows if abs(r["strike"] - atm) <= step * 2]
        n_ce = sum(r["ce"]["oi"] for r in nearby) or 1
        n_pe = sum(r["pe"]["oi"] for r in nearby)
        atm_row = next((r for r in rows if r["strike"] == atm), None)
        atm_pcr = (atm_row["pe"]["oi"] / max(atm_row["ce"]["oi"], 1)) if atm_row else oi_pcr
        nearby_pcr = n_pe / n_ce
        self._hist.append((ts, oi_pcr))
        trend = "flat"
        accel = 0.0
        session_chg = 0.0
        if len(self._hist) >= 2:
            session_chg = oi_pcr - self._hist[0][1]
            if oi_pcr > self._hist[0][1] + 0.03:
                trend = "rising"
            elif oi_pcr < self._hist[0][1] - 0.03:
                trend = "falling"
        if len(self._hist) >= 8:
            mid = len(self._hist) // 2
            first = self._hist[mid][1] - self._hist[0][1]
            second = self._hist[-1][1] - self._hist[mid][1]
            accel = second - first
        return {
            "oi_pcr": round(oi_pcr, 3),
            "volume_pcr": round(vol_pcr, 3),
            "atm_pcr": round(atm_pcr, 3),
            "nearby_pcr": round(nearby_pcr, 3),
            "trend": trend,
            "acceleration": round(accel, 4),
            "session_change": round(session_chg, 3),
            "emits_signal": False,
            "note": "PCR is context only and never independently generates a trade signal.",
        }
