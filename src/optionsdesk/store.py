"""SQLite persistence. Standard library only; one file, safe for a single process.

``risk_events`` is append-only: SQL triggers abort any UPDATE or DELETE so the audit trail
cannot be rewritten through this connection (or any other sqlite client honouring triggers).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from optionsdesk.models import (
    DayStatus,
    Direction,
    EligibilityStatus,
    ExitReason,
    RiskEvent,
    SignalIn,
    SignalRecord,
    StrategyRegistration,
    Tier,
    Trade,
    TradeStatus,
)
from optionsdesk.risk_governor import RiskState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_state (
    trading_day TEXT PRIMARY KEY,
    armed_for_day TEXT,
    trades_today INTEGER NOT NULL DEFAULT 0,
    losses_today INTEGER NOT NULL DEFAULT 0,
    realized_pnl_today REAL NOT NULL DEFAULT 0,
    day_status TEXT NOT NULL,
    loss_stop_cleared INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    trading_day TEXT NOT NULL,
    event TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    trades_today INTEGER NOT NULL,
    losses_today INTEGER NOT NULL,
    realized_pnl_today REAL NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    signal_id INTEGER,
    trade_id INTEGER,
    details TEXT NOT NULL DEFAULT '{}'
);
CREATE TRIGGER IF NOT EXISTS risk_events_no_update BEFORE UPDATE ON risk_events
BEGIN SELECT RAISE(ABORT, 'risk_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS risk_events_no_delete BEFORE DELETE ON risk_events
BEGIN SELECT RAISE(ABORT, 'risk_events is append-only'); END;

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    tradingsymbol TEXT NOT NULL,
    confidence REAL NOT NULL,
    payload TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    tier TEXT,
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    trade_id INTEGER
);
CREATE INDEX IF NOT EXISTS signals_strategy_idx ON signals (strategy_id, received_at);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL,
    strategy_id TEXT NOT NULL,
    tradingsymbol TEXT NOT NULL,
    underlying TEXT NOT NULL,
    direction TEXT NOT NULL,
    lots INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    tier TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    target REAL NOT NULL,
    fill_price REAL,
    exit_price REAL,
    exit_reason TEXT,
    realized_pnl REAL,
    entry_order_id TEXT,
    exit_order_id TEXT,
    created_at TEXT NOT NULL,
    opened_at TEXT,
    closed_at TEXT,
    confirm_deadline TEXT,
    note TEXT
);
CREATE INDEX IF NOT EXISTS trades_status_idx ON trades (status);

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL,
    backtest TEXT,
    tested_at TEXT,
    description TEXT,
    updated_at TEXT NOT NULL
);
"""


def _iso(dt: datetime | date | None) -> str | None:
    return dt.isoformat() if dt else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


class DeskStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL") if self.path != ":memory:" else None
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- risk state / events

    def load_latest_state(self) -> RiskState | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM risk_state ORDER BY trading_day DESC LIMIT 1").fetchone()
        if not row:
            return None
        return RiskState(
            trading_day=date.fromisoformat(row["trading_day"]),
            armed_for_day=_d(row["armed_for_day"]),
            trades_today=row["trades_today"],
            losses_today=row["losses_today"],
            realized_pnl_today=row["realized_pnl_today"],
            day_status=DayStatus(row["day_status"]),
            loss_stop_cleared=bool(row["loss_stop_cleared"]),
        )

    def save_state(self, state: RiskState, events: Iterable[RiskEvent], now: datetime) -> list[RiskEvent]:
        """Persist state and append events atomically. Returns the events with ids assigned."""
        saved: list[RiskEvent] = []
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.execute(
                    """INSERT INTO risk_state (trading_day, armed_for_day, trades_today, losses_today,
                       realized_pnl_today, day_status, loss_stop_cleared, updated_at)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(trading_day) DO UPDATE SET
                         armed_for_day=excluded.armed_for_day, trades_today=excluded.trades_today,
                         losses_today=excluded.losses_today, realized_pnl_today=excluded.realized_pnl_today,
                         day_status=excluded.day_status, loss_stop_cleared=excluded.loss_stop_cleared,
                         updated_at=excluded.updated_at""",
                    (
                        state.trading_day.isoformat(),
                        _iso(state.armed_for_day),
                        state.trades_today,
                        state.losses_today,
                        state.realized_pnl_today,
                        state.day_status.value,
                        int(state.loss_stop_cleared),
                        now.isoformat(),
                    ),
                )
                for ev in events:
                    cur = self._conn.execute(
                        """INSERT INTO risk_events (created_at, trading_day, event, from_status, to_status,
                           trades_today, losses_today, realized_pnl_today, actor, reason, signal_id, trade_id, details)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            now.isoformat(),
                            ev.trading_day.isoformat(),
                            ev.event,
                            ev.from_status.value,
                            ev.to_status.value,
                            ev.trades_today,
                            ev.losses_today,
                            ev.realized_pnl_today,
                            ev.actor,
                            ev.reason,
                            ev.signal_id,
                            ev.trade_id,
                            json.dumps(ev.details, default=str),
                        ),
                    )
                    saved.append(ev.model_copy(update={"id": cur.lastrowid, "created_at": now}))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return saved

    def list_risk_events(self, limit: int = 200, trading_day: date | None = None) -> list[RiskEvent]:
        q = "SELECT * FROM risk_events"
        params: list[Any] = []
        if trading_day:
            q += " WHERE trading_day = ?"
            params.append(trading_day.isoformat())
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [
            RiskEvent(
                id=r["id"],
                created_at=_dt(r["created_at"]),
                trading_day=date.fromisoformat(r["trading_day"]),
                event=r["event"],
                from_status=DayStatus(r["from_status"]),
                to_status=DayStatus(r["to_status"]),
                trades_today=r["trades_today"],
                losses_today=r["losses_today"],
                realized_pnl_today=r["realized_pnl_today"],
                actor=r["actor"],
                reason=r["reason"],
                signal_id=r["signal_id"],
                trade_id=r["trade_id"],
                details=json.loads(r["details"] or "{}"),
            )
            for r in rows
        ]

    # ---------------------------------------------------------------- signals

    def insert_signal(
        self,
        payload: SignalIn,
        *,
        now: datetime,
        accepted: bool,
        tier: Tier | None,
        reason_code: str,
        reason: str,
        eligibility: EligibilityStatus,
    ) -> SignalRecord:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO signals (received_at, strategy_id, tradingsymbol, confidence, payload, accepted,
                   tier, reason_code, reason, eligibility) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    now.isoformat(),
                    payload.strategy_id,
                    payload.tradingsymbol,
                    payload.confidence,
                    payload.model_dump_json(),
                    int(accepted),
                    tier.value if tier else None,
                    reason_code,
                    reason,
                    eligibility.value,
                ),
            )
        return SignalRecord(
            id=cur.lastrowid,
            received_at=now,
            payload=payload,
            accepted=accepted,
            tier=tier,
            reason_code=reason_code,
            reason=reason,
            eligibility=eligibility,
        )

    def update_signal_outcome(
        self, signal_id: int, *, accepted: bool, reason_code: str, reason: str, trade_id: int | None
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE signals SET accepted=?, reason_code=?, reason=?, trade_id=? WHERE id=?",
                (int(accepted), reason_code, reason, trade_id, signal_id),
            )

    def recent_confidences(self, strategy_id: str, limit: int = 200) -> list[float]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT confidence FROM signals WHERE strategy_id=? ORDER BY id DESC LIMIT ?",
                (strategy_id, limit),
            ).fetchall()
        return [r["confidence"] for r in rows]

    def get_signal(self, signal_id: int) -> SignalRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
        return self._signal(row) if row else None

    def list_signals(self, limit: int = 100) -> list[SignalRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._signal(r) for r in rows]

    @staticmethod
    def _signal(r: sqlite3.Row) -> SignalRecord:
        return SignalRecord(
            id=r["id"],
            received_at=_dt(r["received_at"]),  # type: ignore[arg-type]
            payload=SignalIn.model_validate_json(r["payload"]),
            accepted=bool(r["accepted"]),
            tier=Tier(r["tier"]) if r["tier"] else None,
            reason_code=r["reason_code"],
            reason=r["reason"],
            eligibility=EligibilityStatus(r["eligibility"]),
            trade_id=r["trade_id"],
        )

    # ---------------------------------------------------------------- trades

    _TRADE_COLUMNS = frozenset(
        {
            "signal_id",
            "strategy_id",
            "tradingsymbol",
            "underlying",
            "direction",
            "lots",
            "quantity",
            "tier",
            "mode",
            "status",
            "entry_price",
            "stop_loss",
            "target",
            "fill_price",
            "exit_price",
            "exit_reason",
            "realized_pnl",
            "entry_order_id",
            "exit_order_id",
            "created_at",
            "opened_at",
            "closed_at",
            "confirm_deadline",
            "note",
        }
    )

    def insert_trade(self, trade: dict[str, Any]) -> Trade:
        cols = [
            "signal_id",
            "strategy_id",
            "tradingsymbol",
            "underlying",
            "direction",
            "lots",
            "quantity",
            "tier",
            "mode",
            "status",
            "entry_price",
            "stop_loss",
            "target",
            "fill_price",
            "exit_price",
            "exit_reason",
            "realized_pnl",
            "entry_order_id",
            "exit_order_id",
            "created_at",
            "opened_at",
            "closed_at",
            "confirm_deadline",
            "note",
        ]
        values = [self._enc(trade.get(c)) for c in cols]
        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO trades ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", values
            )
            return self.get_trade(cur.lastrowid)  # type: ignore[return-value]

    def update_trade(self, trade_id: int, **fields: Any) -> Trade:
        if not fields:
            return self.get_trade(trade_id)  # type: ignore[return-value]
        unknown = set(fields) - self._TRADE_COLUMNS
        if unknown:
            raise ValueError(f"unknown trade columns: {sorted(unknown)}")
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self._conn.execute(
                f"UPDATE trades SET {sets} WHERE id=?", [*(self._enc(v) for v in fields.values()), trade_id]
            )
            return self.get_trade(trade_id)  # type: ignore[return-value]

    def get_trade(self, trade_id: int) -> Trade | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        return self._trade(row) if row else None

    def list_trades(self, statuses: Iterable[TradeStatus] | None = None, limit: int = 200) -> list[Trade]:
        q = "SELECT * FROM trades"
        params: list[Any] = []
        if statuses:
            vals = [s.value for s in statuses]
            q += f" WHERE status IN ({','.join('?' * len(vals))})"
            params += vals
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [self._trade(r) for r in rows]

    @staticmethod
    def _enc(v: Any) -> Any:
        if isinstance(v, datetime | date):
            return v.isoformat()
        if hasattr(v, "value"):
            return v.value
        return v

    @staticmethod
    def _trade(r: sqlite3.Row) -> Trade:
        return Trade(
            id=r["id"],
            signal_id=r["signal_id"],
            strategy_id=r["strategy_id"],
            tradingsymbol=r["tradingsymbol"],
            underlying=r["underlying"],
            direction=Direction(r["direction"]),
            lots=r["lots"],
            quantity=r["quantity"],
            tier=Tier(r["tier"]),
            mode=r["mode"],
            status=TradeStatus(r["status"]),
            entry_price=r["entry_price"],
            stop_loss=r["stop_loss"],
            target=r["target"],
            fill_price=r["fill_price"],
            exit_price=r["exit_price"],
            exit_reason=ExitReason(r["exit_reason"]) if r["exit_reason"] else None,
            realized_pnl=r["realized_pnl"],
            entry_order_id=r["entry_order_id"],
            exit_order_id=r["exit_order_id"],
            created_at=_dt(r["created_at"]),  # type: ignore[arg-type]
            opened_at=_dt(r["opened_at"]),
            closed_at=_dt(r["closed_at"]),
            confirm_deadline=_dt(r["confirm_deadline"]),
            note=r["note"],
        )

    # ---------------------------------------------------------------- strategies

    def upsert_strategy(self, reg: StrategyRegistration, now: datetime) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO strategies (strategy_id, code_hash, backtest, tested_at, description, updated_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(strategy_id) DO UPDATE SET code_hash=excluded.code_hash, backtest=excluded.backtest,
                     tested_at=excluded.tested_at, description=excluded.description, updated_at=excluded.updated_at""",
                (
                    reg.strategy_id,
                    reg.code_hash,
                    reg.backtest.model_dump_json() if reg.backtest else None,
                    _iso(reg.tested_at),
                    reg.description,
                    now.isoformat(),
                ),
            )

    def get_strategy(self, strategy_id: str) -> tuple[StrategyRegistration, datetime] | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM strategies WHERE strategy_id=?", (strategy_id,)).fetchone()
        return self._strategy(r) if r else None

    def list_strategies(self) -> list[tuple[StrategyRegistration, datetime]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM strategies ORDER BY strategy_id").fetchall()
        return [self._strategy(r) for r in rows]

    @staticmethod
    def _strategy(r: sqlite3.Row) -> tuple[StrategyRegistration, datetime]:
        from optionsdesk.models import BacktestResult

        reg = StrategyRegistration(
            strategy_id=r["strategy_id"],
            code_hash=r["code_hash"],
            backtest=BacktestResult.model_validate_json(r["backtest"]) if r["backtest"] else None,
            tested_at=_dt(r["tested_at"]),
            description=r["description"],
        )
        return reg, _dt(r["updated_at"])  # type: ignore[return-value]
