"""Desk pipeline: ticks → engines → score → master analyst → signal. No broker."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from backend.analytics.cvd import CvdEngine
from backend.analytics.ict import analyze as analyze_ict
from backend.analytics.news import collect_news, news_bias
from backend.analytics.oi_flow import classify_chain, heatmap
from backend.analytics.option_chain import build_chain
from backend.analytics.pcr import PcrEngine
from backend.analytics.regime import classify as classify_regime
from backend.analytics.volume_ta import VolumeTaEngine
from backend.agents.desk import master_analyst, run_desk
from backend.signals.engine import build_signal
from backend.signals.lifecycle import next_state
from backend.signals.score import compute as compute_score


class DeskPipeline:
    def __init__(self) -> None:
        self.cvd = CvdEngine()
        self.pcr = PcrEngine()
        self.ta = VolumeTaEngine()
        self.candles: list[dict] = []
        self.news: list[dict] = []
        self.current_signal: dict | None = None
        self.chain_depth = 12
        self.last_chain: dict | None = None
        self.last_snapshot: dict = {}

    def ingest_bar(self, bar: dict, persist=None, news: list[dict] | None = None) -> dict:
        if news is not None:
            self.news = news
        candle = {
            "time": bar.get("time") or int(time.time()),
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar.get("volume") or 0,
        }
        self.candles.append(candle)
        ta = self.ta.push(candle)
        cvd = self.cvd.ingest(
            price=bar["close"],
            qty=float(bar.get("qty") or max(int(bar.get("volume") or 0) / 20, 1)),
            bid=bar.get("bid"),
            ask=bar.get("ask"),
            ts=float(bar.get("time") or time.time()),
        )
        chain = build_chain(bar["close"], depth=self.chain_depth)
        self.last_chain = chain
        flow = classify_chain(chain["rows"], chain["atm"])
        heat = heatmap(chain["rows"])
        pcr = self.pcr.compute(chain["rows"], chain["atm"], chain["step"], float(bar.get("time") or time.time()))
        ict = analyze_ict(self.candles)
        regime = classify_regime(ta, cvd, flow)
        news_view = news_bias(self.news)

        evidence = {
            "cvd": {"bias": cvd["bias"], "confidence": 0.7, **cvd},
            "option_flow": {"bias": flow["bias"], "confidence": flow["confidence"], **flow},
            "price_action": {"bias": ta["bias"], "confidence": 0.65, **ta},
            "volume": {"bias": ta["bias"], "confidence": 0.55 if ta.get("volume_spike") else 0.4, **ta},
            "pcr": {"bias": "NEUTRAL", "confidence": 0.2, **pcr},
            "ict": {"bias": ict["bias"], "confidence": 0.5, **ict},
            "news": {"bias": news_view["bias"], "confidence": news_view.get("confidence") or 0.2, **news_view},
            "regime": {"bias": regime["bias"], "confidence": 0.55, **regime},
        }
        score = compute_score(evidence)
        specialists = run_desk(evidence)
        master = master_analyst(evidence, score, specialists)
        signal = build_signal(evidence, bar["close"], ta.get("atr"), score)
        if signal.get("direction") == "NO SIGNAL":
            self.current_signal = signal
        elif signal.get("signal_id"):
            self.current_signal = signal
        elif self.current_signal:
            self.current_signal["state"] = next_state(self.current_signal, bar["close"])
            signal = self.current_signal

        chg = 0.0
        pct = 0.0
        if len(self.candles) >= 2:
            chg = bar["close"] - self.candles[0]["open"]
            pct = chg / self.candles[0]["open"] * 100

        snapshot = {
            "type": "update",
            "spot": bar["close"],
            "change": round(chg, 2),
            "pct": round(pct, 2),
            "vwap": ta.get("vwap"),
            "regime": regime["regime"],
            "bias": master["bias"],
            "score": score["score"],
            "confidence": signal.get("confidence"),
            "candle": candle,
            "candles": self.candles[-200:],
            "cvd": cvd,
            "ta": ta,
            "ict": ict,
            "pcr": pcr,
            "chain": chain,
            "oi_flow": flow,
            "heatmap": heat,
            "regime_detail": regime,
            "news": self.news[:20],
            "score_detail": score,
            "signal": signal,
            "master": master,
            "specialists": specialists,
            "signal_only": True,
            "automated_trading": False,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.last_snapshot = snapshot
        if persist:
            persist(snapshot)
        return snapshot
