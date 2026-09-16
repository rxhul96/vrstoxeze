from backend.health import build


class FakeHub:
    last_ts = 0
    ws_clients = set()
    kite_ok = True
    pipeline = type("P", (), {"last_snapshot": {"spot": 1, "chain": {}, "cvd": {}, "heatmap": {}, "news": [], "master": {}, "ts": "t"}})()
    store = type("S", (), {"query": staticmethod(lambda *_a, **_k: [[1]])})()
    settings = type("C", (), {"is_replay": True, "market_data_mode": "replay", "data_dir": __import__("pathlib").Path(".")})()


def test_health_payload_keys():
    h = build(FakeHub())
    for k in ("kite", "websocket", "nifty", "options", "cvd", "oi", "news", "ai", "database", "signal_only"):
        assert k in h
    assert h["signal_only"] is True
