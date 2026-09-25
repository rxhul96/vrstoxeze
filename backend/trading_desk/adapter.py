"""Single adapter from the analyzer's signal producers to the desk's signal intake.

Every analyzer source (CVD, option-flow/OI, ICT, price action, AI master analyst and the
composite signal engine) is mapped to one ``strategy_id`` in the desk's eligibility registry.
The adapter watches each pipeline snapshot, turns a directional bias *transition* into a
``SignalIn`` for the nearest-expiry ATM NIFTY option and hands it to the same code path as
``POST /desk/signals`` (``DeskEngine.submit_signal``).

Only NSE option tradingsymbols leave this module; anything else is dropped with a log line.
The desk's governor decides whether a submitted signal trades — the adapter never touches a
broker.
"""
from __future__ import annotations

import hashlib
import inspect
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from typing import Any, Callable

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.agents import desk as agents_desk
from backend.analytics import cvd as cvd_mod
from backend.analytics import ict as ict_mod
from backend.analytics import lee_ready
from backend.analytics import oi_flow as oi_mod
from backend.analytics import volume_ta as ta_mod
from backend.signals import engine as signal_engine
from backend.signals import score as score_mod
from backend.trading_desk.contracts import atm_strike, next_expiry, option_symbol
from optionsdesk.instruments import InstrumentRejected, parse_option_symbol, validate_option
from optionsdesk.models import Direction, SignalIn, SignalRecord, StrategyRegistration, StrategyStats, TradeStatus

log = logging.getLogger("nifty.desk.adapter")

DIRECTIONAL = ("BULLISH", "BEARISH")


class AdapterSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=True, alias="DESK_ADAPTER_ENABLED")
    # Comma-separated strategy_ids to wire; empty = every source in SOURCES.
    sources: str = Field(default="", alias="DESK_ADAPTER_SOURCES")
    min_confidence: float = Field(default=0.6, ge=0, le=1, alias="DESK_ADAPTER_MIN_CONFIDENCE")
    cooldown_sec: int = Field(default=300, ge=0, alias="DESK_ADAPTER_COOLDOWN_SEC")
    # ATM option delta used to translate spot-point targets/stops into premium moves.
    atm_delta: float = Field(default=0.5, gt=0, le=1, alias="DESK_ADAPTER_ATM_DELTA")
    underlying: str = Field(default="NIFTY", alias="DESK_ADAPTER_UNDERLYING")
    strike_step: int = Field(default=50, ge=1, alias="DESK_ADAPTER_STRIKE_STEP")
    # NIFTY weekly expiry weekday (Mon=0). NSE moved index expiries to Tuesday in Sep 2025.
    expiry_weekday: int = Field(default=1, ge=0, le=6, alias="DESK_NIFTY_EXPIRY_WEEKDAY")
    min_premium: float = Field(default=5.0, gt=0, alias="DESK_ADAPTER_MIN_PREMIUM")

    def enabled_ids(self) -> set[str] | None:
        ids = {s.strip() for s in self.sources.split(",") if s.strip()}
        return ids or None


@dataclass(frozen=True)
class SourceSignal:
    bias: str
    confidence: float
    reason: str = ""
    # Spot-level target / invalidation when the source provides them (composite signal).
    target: float | None = None
    invalidation: float | None = None


@dataclass(frozen=True)
class SourceSpec:
    strategy_id: str
    description: str
    modules: tuple[ModuleType, ...]
    extract: Callable[[dict], SourceSignal | None]


# ----------------------------------------------------------------------------- extractors


def _composite(snap: dict) -> SourceSignal | None:
    sig = snap.get("signal") or {}
    if not sig.get("signal_id") or sig.get("direction") not in DIRECTIONAL:
        return None
    if sig.get("state") in ("INVALIDATED", "EXPIRED"):
        return None
    return SourceSignal(
        bias=sig["direction"],
        confidence=float(sig.get("confidence") or 0.0),
        reason="; ".join(sig.get("reasons") or [])[:200],
        target=sig.get("target_1"),
        invalidation=sig.get("invalidation"),
    )


def _cvd(snap: dict) -> SourceSignal | None:
    cvd = snap.get("cvd") or {}
    bias = cvd.get("bias")
    if bias not in DIRECTIONAL:
        return None
    # The pipeline weights CVD evidence at 0.7; an explicit event (divergence/genuine flow) adds conviction.
    conf = 0.75 if cvd.get("event") else 0.7
    return SourceSignal(bias=bias, confidence=conf, reason=str(cvd.get("event") or cvd.get("label") or ""))


def _oi_flow(snap: dict) -> SourceSignal | None:
    flow = snap.get("oi_flow") or {}
    bias = flow.get("bias")
    if bias not in DIRECTIONAL:
        return None
    ce = (flow.get("call") or {}).get("label")
    pe = (flow.get("put") or {}).get("label")
    return SourceSignal(bias=bias, confidence=float(flow.get("confidence") or 0.0), reason=f"CE {ce} / PE {pe}")


def _ict(snap: dict) -> SourceSignal | None:
    ict = snap.get("ict") or {}
    bias = ict.get("bias")
    if bias not in DIRECTIONAL:
        return None
    events = ict.get("events") or []
    return SourceSignal(
        bias=bias,
        confidence=min(0.8, 0.5 + 0.05 * len(events)),
        reason=", ".join(str(e.get("type") if isinstance(e, dict) else e) for e in events[:4]),
    )


def _price_action(snap: dict) -> SourceSignal | None:
    ta = snap.get("ta") or {}
    bias = ta.get("bias")
    if bias not in DIRECTIONAL:
        return None
    return SourceSignal(
        bias=bias,
        confidence=0.75 if ta.get("volume_spike") else 0.65,
        reason=str(ta.get("event") or ta.get("structure") or ""),
    )


def _ai_master(snap: dict) -> SourceSignal | None:
    master = snap.get("master") or {}
    bias = master.get("bias")
    if bias not in DIRECTIONAL or not str(master.get("headline") or "").startswith("MASTER BIAS"):
        return None
    raw = abs(float((snap.get("score_detail") or {}).get("raw") or 0.0))
    return SourceSignal(bias=bias, confidence=min(0.9, 0.5 + raw / 200), reason=str(master.get("headline") or ""))


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "composite_score",
        "Signal engine: frozen-weight institutional score -> CALL/PUT BUY BIAS with T1/invalidation",
        (signal_engine, score_mod),
        _composite,
    ),
    SourceSpec("cvd_flow", "Estimated CVD (Lee-Ready tick rule) bias transitions", (cvd_mod, lee_ready), _cvd),
    SourceSpec("oi_flow", "Option-chain OI change x price change flow classification", (oi_mod,), _oi_flow),
    SourceSpec("ict_liquidity", "ICT liquidity sweeps / displacement from OHLC", (ict_mod,), _ict),
    SourceSpec("price_action_ta", "VWAP / EMA / RSI structure with volume confirmation", (ta_mod,), _price_action),
    SourceSpec("ai_master_analyst", "MasterAnalyst synthesis of the specialist agent desk", (agents_desk,), _ai_master),
)


def code_hash(modules: tuple[ModuleType, ...]) -> str:
    """Stable hash of the producing modules' source so the registry can flag STALE strategies."""
    h = hashlib.sha256()
    for m in modules:
        try:
            h.update(inspect.getsource(m).encode("utf-8"))
        except (OSError, TypeError):  # frozen bundle without sources
            h.update(f"{m.__name__}:{getattr(m, '__file__', '')}".encode("utf-8"))
    return h.hexdigest()[:32]


# ----------------------------------------------------------------------------- adapter


class SignalAdapter:
    """Edge-triggered bridge: one ``SignalIn`` per bias transition per source, rate limited."""

    def __init__(
        self,
        engine: Any,
        settings: AdapterSettings | None = None,
        sink: Callable[[SignalIn], SignalRecord] | None = None,
    ) -> None:
        self.engine = engine
        self.settings = settings or AdapterSettings()
        self.sink = sink or (lambda sig: engine.submit_signal(sig, actor="analyzer"))
        wanted = self.settings.enabled_ids()
        self.sources = tuple(s for s in SOURCES if wanted is None or s.strategy_id in wanted)
        self.code_hashes = {s.strategy_id: code_hash(s.modules) for s in self.sources}
        self._last_emitted_bias: dict[str, str] = {}
        self._last_emit_at: dict[str, datetime] = {}
        self.counters = {"emitted": 0, "accepted": 0, "governor_rejected": 0, "dropped": 0, "errors": 0}
        self.recent: deque[dict] = deque(maxlen=50)

    # -- registry ---------------------------------------------------------------------------

    def register_strategies(self) -> list[str]:
        """Register every wired source once (NOT_TESTED until backtest results are posted).

        Existing records are left alone so an operator's backtest is never overwritten; the
        signal's ``code_hash`` lets the registry flag a strategy STALE if the code changed.
        """
        now = self.engine.clock.now()
        created = []
        for src in self.sources:
            if self.engine.registry.get(src.strategy_id, now) is None:
                self.engine.registry.register(
                    StrategyRegistration(
                        strategy_id=src.strategy_id,
                        code_hash=self.code_hashes[src.strategy_id],
                        description=src.description[:300],
                    ),
                    now,
                )
                created.append(src.strategy_id)
        return created

    # -- snapshot intake ----------------------------------------------------------------------

    def on_snapshot(self, snap: dict) -> list[dict]:
        if not self.settings.enabled or not snap:
            return []
        try:
            self._push_prices(snap)
        except Exception as exc:  # noqa: BLE001
            log.warning("desk price push failed: %s", exc)
        out: list[dict] = []
        for src in self.sources:
            try:
                res = self._process(src, snap)
            except Exception as exc:  # noqa: BLE001 - the analyzer pipeline must never die here
                self.counters["errors"] += 1
                log.exception("adapter error for %s: %s", src.strategy_id, exc)
                continue
            if res:
                out.append(res)
                self.recent.appendleft(res)
        return out

    def _process(self, src: SourceSpec, snap: dict) -> dict | None:
        sid = src.strategy_id
        ss = src.extract(snap)
        bias = ss.bias if ss else "NEUTRAL"
        if bias not in DIRECTIONAL:
            self._last_emitted_bias[sid] = "NEUTRAL"  # re-arm the edge
            return None
        if self._last_emitted_bias.get(sid) == bias:
            return None
        assert ss is not None
        if ss.confidence < self.settings.min_confidence:
            log.debug("%s: %s below min confidence (%.2f < %.2f)", sid, bias, ss.confidence, self.settings.min_confidence)
            return None
        now = self.engine.clock.now()
        last = self._last_emit_at.get(sid)
        if last is not None and (now - last).total_seconds() < self.settings.cooldown_sec:
            log.debug("%s: cooldown active, holding %s", sid, bias)
            return None

        try:
            sig = self.build_signal(src, ss, snap, now)
        except InstrumentRejected as exc:
            self.counters["dropped"] += 1
            self._last_emitted_bias[sid] = bias
            log.warning("DROPPED non-NSE-option signal from %s (%s): %s", sid, bias, exc)
            return {"strategy_id": sid, "outcome": "dropped", "reason": str(exc), "ts": now.isoformat()}

        self._last_emitted_bias[sid] = bias
        self._last_emit_at[sid] = now
        self.counters["emitted"] += 1
        try:
            rec = self.sink(sig)
        except InstrumentRejected as exc:
            self.counters["dropped"] += 1
            log.warning("desk refused %s %s: %s", sid, sig.tradingsymbol, exc)
            return {"strategy_id": sid, "tradingsymbol": sig.tradingsymbol, "outcome": "dropped", "reason": str(exc), "ts": now.isoformat()}
        except Exception as exc:  # noqa: BLE001 - DeskError / BrokerError / HTTP sink failures
            self.counters["errors"] += 1
            log.error("desk submit failed for %s %s: %s", sid, sig.tradingsymbol, exc)
            return {"strategy_id": sid, "tradingsymbol": sig.tradingsymbol, "outcome": "error", "reason": str(exc), "ts": now.isoformat()}

        self.counters["accepted" if rec.accepted else "governor_rejected"] += 1
        log.info(
            "desk signal %s %s %s -> %s (%s)", sid, sig.direction.value, sig.tradingsymbol,
            "ACCEPTED" if rec.accepted else "REJECTED", rec.reason_code,
        )
        return {
            "strategy_id": sid,
            "tradingsymbol": sig.tradingsymbol,
            "outcome": "accepted" if rec.accepted else "rejected",
            "reason_code": rec.reason_code,
            "reason": rec.reason,
            "tier": rec.tier.value if rec.tier else None,
            "trade_id": rec.trade_id,
            "desk_signal_id": rec.id,
            "ts": now.isoformat(),
        }

    # -- mapping ------------------------------------------------------------------------------

    def build_signal(self, src: SourceSpec, ss: SourceSignal, snap: dict, now: datetime) -> SignalIn:
        """Map a directional analyzer bias onto a BUY of the nearest-expiry ATM CE/PE."""
        cfg = self.settings
        spot = float(snap.get("spot") or 0.0)
        if spot <= 0:
            raise InstrumentRejected("snapshot has no spot price")
        instrument_type = str((snap.get("signal") or {}).get("instrument_type") or cfg.underlying).upper()
        if instrument_type != cfg.underlying.upper():
            raise InstrumentRejected(f"instrument_type {instrument_type!r} is not the configured option underlying")

        chain = snap.get("chain") or {}
        strike = int(chain.get("atm") or atm_strike(spot, cfg.strike_step))
        kind = "CE" if ss.bias == "BULLISH" else "PE"
        expiry, monthly = next_expiry(now, cfg.expiry_weekday)
        symbol = option_symbol(cfg.underlying, expiry, monthly, strike, kind)

        atr = float((snap.get("ta") or {}).get("atr") or 0.0) or max(spot * 0.0025, 20.0)
        target_pts = abs(ss.target - spot) if ss.target else atr * 1.0
        stop_pts = abs(spot - ss.invalidation) if ss.invalidation else atr * 1.1
        premium = self._chain_premium(chain, strike, kind)
        entry = round(premium if premium else max(cfg.min_premium, atr * cfg.atm_delta), 2)
        target = round(entry + target_pts * cfg.atm_delta, 2)
        # Premium stop: delta-scaled invalidation distance, but never more than 70% of the premium.
        stop_loss = round(max(entry - stop_pts * cfg.atm_delta, entry * 0.3), 2)
        if not (0 < stop_loss < entry < target):
            raise InstrumentRejected(f"degenerate premium levels sl={stop_loss} entry={entry} target={target}")

        sig = SignalIn(
            strategy_id=src.strategy_id,
            code_hash=self.code_hashes[src.strategy_id],
            tradingsymbol=symbol,
            exchange="NFO",
            direction=Direction.BUY,
            entry=entry,
            stop_loss=stop_loss,
            target=target,
            confidence=max(0.0, min(1.0, ss.confidence)),
            stats=self._stats(src.strategy_id, now),
            note=f"{src.strategy_id}: {ss.bias} — {ss.reason}"[:500],
            meta={
                "source": src.strategy_id,
                "bias": ss.bias,
                "spot": spot,
                "strike": strike,
                "expiry": expiry.isoformat(),
                "monthly": monthly,
                "atr": round(atr, 2),
                "analyzer_signal_id": (snap.get("signal") or {}).get("signal_id"),
                "snapshot_ts": snap.get("ts"),
            },
        )
        # Hard gate: nothing but an NFO option tradingsymbol leaves the adapter.
        validate_option(sig.tradingsymbol, sig.exchange)
        return sig

    @staticmethod
    def _chain_premium(chain: dict, strike: int, kind: str) -> float | None:
        for row in chain.get("rows") or []:
            if int(row.get("strike", -1)) == strike:
                ltp = (row.get(kind.lower()) or {}).get("ltp")
                return float(ltp) if ltp else None
        return None

    def _stats(self, strategy_id: str, now: datetime) -> StrategyStats:
        closed = [
            t
            for t in self.engine.store.list_trades([TradeStatus.CLOSED], limit=1000)
            if t.strategy_id == strategy_id and t.realized_pnl is not None
        ]
        win_rate = (sum(1 for t in closed if t.realized_pnl > 0) / len(closed)) if closed else None
        rec = self.engine.registry.get(strategy_id, now)
        oos = rec.backtest.oos_sharpe if rec and rec.backtest else None
        return StrategyStats(live_win_rate=win_rate, live_trades=len(closed), oos_sharpe=oos)

    # -- prices -------------------------------------------------------------------------------

    def _push_prices(self, snap: dict) -> None:
        """Mark open desk trades from the analyzer's option chain so SL/target exits fire."""
        open_trades = self.engine.store.list_trades([TradeStatus.OPEN])
        if not open_trades:
            return
        rows = {int(r["strike"]): r for r in (snap.get("chain") or {}).get("rows") or [] if "strike" in r}
        prices: dict[str, float] = {}
        for t in open_trades:
            try:
                inst = parse_option_symbol(t.tradingsymbol)
            except InstrumentRejected:
                continue
            if inst.underlying != self.settings.underlying.upper():
                continue
            leg = (rows.get(int(inst.strike)) or {}).get(inst.option_type.lower()) or {}
            if leg.get("ltp"):
                prices[t.tradingsymbol] = float(leg["ltp"])
        if prices:
            self.engine.on_prices(prices)

    # -- status -------------------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "enabled": self.settings.enabled,
            "sources": [
                {"strategy_id": s.strategy_id, "code_hash": self.code_hashes[s.strategy_id], "description": s.description}
                for s in self.sources
            ],
            "min_confidence": self.settings.min_confidence,
            "cooldown_sec": self.settings.cooldown_sec,
            "underlying": self.settings.underlying,
            "counters": dict(self.counters),
            "recent": list(self.recent)[:10],
        }
