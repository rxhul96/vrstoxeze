from datetime import datetime

from backend.market import IST, is_nse_holiday, is_trading_day, session_phase, session_state
from backend.session.runner import SessionRunner
from backend.storage.db import Store
from backend.feed.replay import session_tape
from backend.pipeline import DeskPipeline


def test_republic_day_is_holiday():
    d = datetime(2026, 1, 26, 10, 0, tzinfo=IST)
    assert is_nse_holiday(d)
    assert not is_trading_day(d)
    assert session_phase(d) == "idle"


def test_runner_collects_only_in_session(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/s.sqlite")
    r = SessionRunner(store, kite_ok=lambda: True)
    morning = datetime(2026, 9, 16, 10, 0, tzinfo=IST)  # Wednesday
    st = r.tick(morning)
    assert st["collecting"] is True
    after = datetime(2026, 9, 16, 16, 0, tzinfo=IST)
    st2 = r.tick(after)
    assert st2["collecting"] is False


def test_replay_tape_starts_at_open():
    tape = session_tape("2026-09-16", bars=10)
    assert "T09:15:00" in tape[0]["ts"]
    assert tape[0]["close"] > 0


def test_pipeline_and_store_replay(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/p.sqlite")
    pipe = DeskPipeline()
    tape = session_tape("2026-09-16", bars=15)
    last = None
    for bar in tape:
        last = pipe.ingest_bar(bar)
        store.insert_json("cvd_snapshots", bar["ts"], last["cvd"])
        store.execute(
            "INSERT INTO ticks (ts, instrument, ltp, volume) VALUES (?,?,?,?)",
            (bar["ts"], "NIFTY", bar["close"], bar["volume"]),
        )
    rows = store.replay("ticks", "2026-09-16T09:15:00")
    assert len(rows) == 15
    assert last["spot"]
    assert last["cvd"]["methodology"] == "ESTIMATED CVD"
    assert last["signal_only"] is True
    assert last["chain"]["rows"]
    assert last["pcr"]["emits_signal"] is False
    mixed = DeskPipeline()
    from backend.signals.engine import build_signal
    from backend.signals.score import compute
    ev = {
        "cvd": {"bias": "BULLISH", "confidence": 0.8},
        "option_flow": {"bias": "BEARISH", "confidence": 0.8},
        "price_action": {"bias": "NEUTRAL", "confidence": 0.5},
        "volume": {"bias": "NEUTRAL", "confidence": 0.4},
        "pcr": {"bias": "NEUTRAL", "confidence": 0.2},
        "ict": {"bias": "NEUTRAL", "confidence": 0.4},
        "news": {"bias": "NEUTRAL", "confidence": 0.2},
        "regime": {"bias": "NEUTRAL", "confidence": 0.4},
    }
    out = build_signal(ev, 25000, 40, compute(ev))
    assert out["direction"] == "NO SIGNAL"


def test_session_state_shape():
    st = session_state(datetime(2026, 9, 16, 11, 0, tzinfo=IST))
    assert st["open"] is True
    assert st["phase"] == "collect"
