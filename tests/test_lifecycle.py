from backend.signals.engine import build_signal
from backend.signals.lifecycle import next_state
from backend.signals.paper_track import grade
from backend.signals.score import compute


def _bull():
    keys = ["cvd", "option_flow", "price_action", "volume", "pcr", "ict", "news", "regime"]
    ev = {k: {"bias": "BULLISH", "confidence": 0.85} for k in keys}
    ev["pcr"] = {"bias": "NEUTRAL", "confidence": 0.2}
    s = compute(ev)
    return build_signal(ev, 25000, 50, s)


def test_lifecycle_invalidation_and_targets():
    sig = _bull()
    assert sig["direction"] == "BULLISH"
    sig["state"] = "TRIGGERED"
    assert next_state(sig, sig["invalidation"] - 1) == "INVALIDATED"
    assert next_state(sig, sig["target_2"] + 1) == "TARGET 2 REACHED"


def test_paper_track_no_broker():
    sig = _bull()
    start = 25000
    closes = [start + i for i in range(0, 80, 5)]
    g = grade(sig, closes)
    assert g["broker"] is None
    assert "broker" in g["note"].lower() or "no broker" in g["note"].lower()
    assert g["outcome"] in {"true", "false", "open"}
