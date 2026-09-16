"""Always-on session runner. Collects even when the desktop is closed."""
from __future__ import annotations

import logging
from datetime import datetime

from backend.market import now_ist, session_phase, session_state, is_trading_day
from backend.storage.db import Store

log = logging.getLogger("nifty.session")

PHASE_ORDER = (
    "idle",
    "init",
    "kite_auth",
    "sync_instruments",
    "premarket",
    "collect",
    "stopping",
    "finalize",
    "report",
    "archive",
)


class SessionRunner:
    def __init__(self, store: Store, kite_ok: callable | None = None):
        self.store = store
        self.kite_ok = kite_ok or (lambda: True)
        self.phase = "idle"
        self.collecting = False
        self.kite_login_required = False
        self.last_state: dict = {}

    def tick(self, dt: datetime | None = None) -> dict:
        dt = dt or now_ist()
        state = session_state(dt)
        phase = session_phase(dt)
        self.phase = phase
        day = dt.strftime("%Y-%m-%d")
        if not is_trading_day(dt):
            self.collecting = False
            state["phase"] = "idle"
            state["reason"] = "weekend_or_holiday"
            self.last_state = state
            return state

        if phase in ("init", "kite_auth", "sync_instruments", "premarket"):
            self.store.upsert_session(day, phase, started_at=dt.isoformat())
            if phase == "kite_auth" and not self.kite_ok():
                self.kite_login_required = True
            else:
                self.kite_login_required = False

        self.collecting = phase == "collect" and not self.kite_login_required
        if phase == "finalize":
            self.collecting = False
            self.store.upsert_session(day, "finalize", finalized_at=dt.isoformat())
        if phase == "archive":
            from backend.config import get_settings
            dest = get_settings().data_dir / "archive" / f"ticks-{day}.json"
            n = self.store.archive_old_ticks(get_settings().archive_after_days, dest)
            state["archived_ticks"] = n
        state["collecting"] = self.collecting
        state["kite_login_required"] = self.kite_login_required
        state["signals_paused"] = self.kite_login_required or not self.collecting and phase == "collect"
        self.last_state = state
        return state
