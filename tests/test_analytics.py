from backend.analytics.cvd import CvdEngine
from backend.analytics.pcr import PcrEngine
from backend.analytics.oi_flow import classify_leg, heatmap
from backend.analytics.option_chain import build_chain
from backend.analytics.news import recency_weight, news_bias, enrich
from backend.analytics.regime import classify
from backend.analytics.ict import analyze


def test_cvd_is_labeled_estimated():
    e = CvdEngine()
    e.ingest(100, 10, bid=99.9, ask=100.1)
    e.ingest(100.2, 12, bid=100.0, ask=100.3)
    snap = e.snapshot(100.2)
    assert snap["methodology"] == "ESTIMATED CVD"
    assert "aggressor" not in snap["methodology_note"].lower() or "does not provide" in snap["methodology_note"].lower()
    assert snap["buy_volume"] > 0


def test_option_flow_patterns():
    assert classify_leg(1000, -2, 20000)["label"] == "writing"
    assert classify_leg(1000, 2, 20000)["label"] == "buying"
    assert classify_leg(-1000, 2, 20000)["label"] == "short_covering"
    assert classify_leg(-1000, -2, 20000)["label"] == "long_unwinding"


def test_heatmap_uses_delta_not_total_oi():
    rows = [
        {"strike": 25000, "ce": {"oi": 9_000_000, "doi": 10}, "pe": {"oi": 1000, "doi": -5000}},
        {"strike": 25050, "ce": {"oi": 1000, "doi": 8000}, "pe": {"oi": 1000, "doi": 10}},
    ]
    h = heatmap(rows)
    # The large total OI row with tiny ΔOI must not dominate intensity.
    by = {x["strike"]: x for x in h}
    assert abs(by[25050]["ce_intensity"]) > abs(by[25000]["ce_intensity"])


def test_pcr_never_emits_signal():
    chain = build_chain(25000, depth=4)
    p = PcrEngine().compute(chain["rows"], chain["atm"], chain["step"], 1.0)
    assert p["emits_signal"] is False
    assert "oi_pcr" in p


def test_news_decay():
    assert recency_weight(0, now=0) == 1.0
    assert recency_weight(0, now=90 * 60) == 0.5
    items = [enrich({"source": "x", "headline": "old", "sentiment": "BULLISH", "relevance": 1, "impact": "high", "confidence": 1}, ts=0)]
    # very old → discounted toward neutral
    b = news_bias([{**items[0], "effective_relevance": 0.01, "ts": 0}])
    assert b["bias"] == "NEUTRAL"


def test_ict_from_candles_only():
    candles = []
    px = 100.0
    for i in range(30):
        candles.append({"open": px, "high": px + 1, "low": px - 1, "close": px + 0.2})
        px += 0.2
    out = analyze(candles)
    assert "session_high" in out
    assert isinstance(out["events"], list)


def test_regime_labels():
    r = classify({"structure": "uptrend", "event": None, "atr": 40, "close": 25000, "rvol": 1.1}, {"bias": "BULLISH"})
    assert r["regime"] in r["allowed"]
    assert r["bias"] == "BULLISH"
