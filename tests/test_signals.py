from backend.signals.score import WEIGHTS, compute
from backend.signals.engine import build_signal


def test_weights_locked_and_sum_100():
    assert sum(WEIGHTS.values()) == 100
    assert WEIGHTS["cvd"] == 20
    assert WEIGHTS["option_flow"] == 20
    assert WEIGHTS["price_action"] == 20
    assert WEIGHTS["volume"] == 10
    assert WEIGHTS["pcr"] == 10
    assert WEIGHTS["ict"] == 10
    assert WEIGHTS["news"] == 5
    assert WEIGHTS["regime"] == 5


def _ev(**biases):
    keys = ["cvd", "option_flow", "price_action", "volume", "pcr", "ict", "news", "regime"]
    return {k: {"bias": biases.get(k, "NEUTRAL"), "confidence": 0.8} for k in keys}


def test_aligned_bullish_score():
    s = compute(_ev(cvd="BULLISH", option_flow="BULLISH", price_action="BULLISH", volume="BULLISH", ict="BULLISH", regime="BULLISH"))
    assert s["bias"] == "BULLISH"
    assert s["weights_locked"] is True
    sig = build_signal(_ev(cvd="BULLISH", option_flow="BULLISH", price_action="BULLISH", volume="BULLISH", ict="BULLISH", regime="BULLISH"), 25000, 40, s)
    assert sig["direction"] == "BULLISH"
    assert sig["signal_type"] == "CALL BUY BIAS"
    assert sig["entry_zone"]
    assert sig["target_1"]
    assert sig["invalidation"]
    assert sig["execution"].startswith("SIGNAL-ONLY")


def test_mixed_evidence_is_no_signal():
    ev = _ev(cvd="BULLISH", option_flow="BEARISH", price_action="NEUTRAL", volume="NEUTRAL", news="NEUTRAL")
    s = compute(ev)
    sig = build_signal(ev, 25000, 40, s)
    assert sig["direction"] == "NO SIGNAL"
    assert sig["signal_id"] is None


def test_pcr_cannot_dominate():
    ev = _ev(pcr="BULLISH")
    s = compute(ev)
    # PCR confidence is capped; alone it cannot produce a high-confidence signal.
    sig = build_signal(ev, 25000, 40, s)
    assert sig["direction"] == "NO SIGNAL"
