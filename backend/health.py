"""Live health snapshot for the status bar."""
from __future__ import annotations

import os
import time
from pathlib import Path


def _mem() -> dict:
    try:
        txt = Path("/proc/meminfo").read_text()
        kv = {}
        for line in txt.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                kv[parts[0].rstrip(":")] = int(parts[1])
        total = kv.get("MemTotal") or 1
        avail = kv.get("MemAvailable") or 0
        used_pct = round((1 - avail / total) * 100, 1)
        return {"ram_used_pct": used_pct, "ram_total_kb": total}
    except OSError:
        return {"ram_used_pct": None}


def _cpu() -> float | None:
    try:
        load = os.getloadavg()[0]
        return round(load, 2)
    except OSError:
        return None


def _disk(path: Path) -> dict:
    try:
        s = os.statvfs(path)
        total = s.f_frsize * s.f_blocks
        free = s.f_frsize * s.f_bavail
        return {"disk_used_pct": round((1 - free / total) * 100, 1)}
    except OSError:
        return {}


def build(hub) -> dict:
    now = time.time()
    last = getattr(hub, "last_ts", 0) or 0
    latency_ms = int((now - last) * 1000) if last else None
    stale = last > 0 and (now - last) > 8
    snap = hub.pipeline.last_snapshot if getattr(hub, "pipeline", None) else {}
    kite_ok = bool(getattr(hub, "kite_ok", False))
    ws_ok = bool(getattr(hub, "ws_clients", None))
    db_ok = True
    try:
        hub.store.query("SELECT 1")
    except Exception:
        db_ok = False
    paused = stale or not kite_ok and hub.settings.market_data_mode == "live"
    return {
        "kite": "ok" if kite_ok or hub.settings.is_replay else ("login_required" if not kite_ok else "down"),
        "websocket": "ok" if ws_ok else "idle",
        "nifty": "ok" if snap.get("spot") else "down",
        "options": "ok" if snap.get("chain") else "down",
        "cvd": "ok" if snap.get("cvd") else "down",
        "oi": "ok" if snap.get("heatmap") else "down",
        "news": "ok" if snap.get("news") is not None else "down",
        "ai": "ok" if snap.get("master") else "down",
        "database": "ok" if db_ok else "down",
        "cpu_load": _cpu(),
        **_mem(),
        **_disk(hub.settings.data_dir),
        "latency_ms": latency_ms,
        "last_update": snap.get("ts"),
        "stale": stale,
        "signals_paused": paused,
        "signal_only": True,
        "mode": hub.settings.market_data_mode,
    }
