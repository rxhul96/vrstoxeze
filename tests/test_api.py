"""API smoke + replay bootstrap."""
from fastapi.testclient import TestClient


def test_health_and_snapshot_and_replay():
    from backend.main import app, hub
    from backend.feed.replay import session_tape
    # Seed a bar so snapshot is non-empty without waiting for the loop.
    hub.pipeline.ingest_bar(session_tape("2026-09-16", bars=3)[-1])
    c = TestClient(app)
    h = c.get("/api/health")
    assert h.status_code == 200
    body = h.json()
    assert body["signal_only"] is True
    snap = c.get("/api/snapshot")
    assert snap.status_code == 200
    assert snap.json().get("spot")
    rep = c.get("/api/session/replay")
    assert rep.status_code == 200
    assert "snapshot" in rep.json()
    html = c.get("/")
    assert html.status_code == 200
    assert b"SIGNAL-ONLY MODE" in html.content
    assert b"AUTOMATED TRADING DISABLED" in html.content
    css = c.get("/static/style.css")
    assert css.status_code == 200
    js = c.get("/static/app.js")
    assert js.status_code == 200
    assert b"place_order" not in js.content
