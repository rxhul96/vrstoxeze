"""DeskEngine — wires signals, the risk governor, the eligibility registry and a broker together.

The engine is the only component allowed to call a broker. Every path that can create an
order goes through :meth:`submit_signal` / :meth:`confirm_live`, and both re-run the governor
immediately before placing.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any

from optionsdesk.brokers.base import BrokerAdapter, BrokerError
from optionsdesk.brokers.paper import PaperBroker
from optionsdesk.clock import Clock, SystemClock, is_market_open, session_day
from optionsdesk.config import DeskConfig
from optionsdesk.eligibility import EligibilityThresholds, StrategyRegistry
from optionsdesk.instruments import InstrumentRejected, validate_option
from optionsdesk.models import (
    DayStatus,
    Direction,
    EligibilityStatus,
    ExitReason,
    OrderRequest,
    Position,
    RiskEvent,
    SignalIn,
    SignalRecord,
    Tier,
    Trade,
    TradeStatus,
)
from optionsdesk.risk_governor import (
    ClearRejected,
    RiskLimits,
    RiskState,
    SignalQuality,
    Transition,
    arm,
    clear_stop,
    disarm,
    evaluate_signal,
    fresh_state,
    kill_switch,
    record_trade_closed,
    record_trade_opened,
    roll_day,
)
from optionsdesk.store import DeskStore

log = logging.getLogger("optionsdesk.engine")


class DeskError(ValueError):
    """User-facing error (bad request / conflict); the API maps it to 4xx."""


class DeskEngine:
    def __init__(
        self,
        config: DeskConfig,
        store: DeskStore,
        broker: BrokerAdapter | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.clock = clock or SystemClock()
        self.broker = broker or PaperBroker()
        if self.broker.is_live and not config.allow_live_orders:
            raise DeskError("a live broker was supplied but ALLOW_LIVE_ORDERS is false")
        self.mode = "live" if (self.broker.is_live and config.allow_live_orders) else "paper"
        self.limits = RiskLimits.from_config(config)
        self.registry = StrategyRegistry(store, EligibilityThresholds.from_config(config))
        self._lock = threading.RLock()
        self._price_seen_at: dict[str, datetime] = {}
        now = self.clock.now()
        self._state: RiskState = store.load_latest_state() or fresh_state(session_day(now))
        if store.load_latest_state() is None:
            store.save_state(self._state, [], now)
        self.refresh()

    # ------------------------------------------------------------------ state plumbing

    @property
    def state(self) -> RiskState:
        with self._lock:
            return self._state

    def _apply(self, t: Transition) -> list[RiskEvent]:
        """Persist a governor transition (state + audit events) atomically."""
        with self._lock:
            saved = self.store.save_state(t.state, t.events, self.clock.now())
            self._state = t.state
            for ev in saved:
                log.info("risk_event %s %s->%s %s", ev.event, ev.from_status.value, ev.to_status.value, ev.reason)
            return saved

    def refresh(self) -> None:
        """Roll the session day if needed and expire stale live confirmations."""
        with self._lock:
            now = self.clock.now()
            self._apply(roll_day(self._state, now))
            for t in self.store.list_trades([TradeStatus.PENDING_CONFIRMATION]):
                if t.confirm_deadline and now > t.confirm_deadline:
                    self.store.update_trade(t.id, status=TradeStatus.EXPIRED, note="live confirmation expired")
                    self.store.update_signal_outcome(
                        t.signal_id,
                        accepted=False,
                        reason_code="CONFIRMATION_EXPIRED",
                        reason="live confirmation window elapsed",
                        trade_id=t.id,
                    )

    def status(self) -> dict[str, Any]:
        self.refresh()
        with self._lock:
            now = self.clock.now()
            st = self._state
            open_trades = self.store.list_trades([TradeStatus.OPEN])
            pending = self.store.list_trades([TradeStatus.PENDING_CONFIRMATION])
            return {
                "now": now.isoformat(),
                "mode": self.mode,
                "broker": self.broker.name,
                "market_open": is_market_open(now),
                "armed": st.is_armed(session_day(now)),
                "risk": st.to_dict(),
                "limits": {
                    "max_trades_per_day": self.limits.max_trades_per_day,
                    "max_losses_per_day": self.limits.max_losses_per_day,
                    "base_tier_trades": self.limits.base_tier_trades,
                },
                "open_trades": len(open_trades),
                "pending_confirmations": len(pending),
                "unrealized_pnl": round(sum(p.pnl or 0.0 for p in self._safe_positions()), 2),
                "config": self.config.public_summary(),
            }

    def _safe_positions(self) -> list[Position]:
        try:
            return self.broker.positions()
        except BrokerError as exc:
            log.warning("positions unavailable: %s", exc)
            return []

    def positions(self) -> list[Position]:
        return self._safe_positions()

    # ------------------------------------------------------------------ manual controls

    def arm(self, actor: str = "operator") -> RiskState:
        self.refresh()
        with self._lock:
            today = session_day(self.clock.now())
            if self._state.day_status != DayStatus.ACTIVE:
                raise DeskError(f"cannot arm: desk is {self._state.day_status.value}")
            self._apply(arm(self._state, today, actor=actor))
            return self._state

    def disarm(self, actor: str = "operator") -> RiskState:
        self.refresh()
        with self._lock:
            self._apply(disarm(self._state, actor=actor))
            return self._state

    def clear_stop(self, phrase: str, actor: str = "operator", note: str = "") -> RiskState:
        self.refresh()
        with self._lock:
            try:
                t = clear_stop(
                    self._state,
                    phrase=phrase,
                    expected_phrase=self.config.confirm_phrase,
                    actor=actor,
                    note=note,
                )
            except ClearRejected as exc:
                raise DeskError(str(exc)) from exc
            self._apply(t)
            return self._state

    def kill(self, actor: str = "operator", reason: str = "kill switch") -> dict[str, Any]:
        """Rule 5: stop the day, cancel open orders, flatten positions, close open trades."""
        self.refresh()
        with self._lock:
            self._apply(kill_switch(self._state, actor=actor, reason=reason))
            report: dict[str, Any] = {
                "cancelled_orders": [],
                "flatten_orders": [],
                "closed_trades": [],
                "errors": [],
            }
            for t in self.store.list_trades([TradeStatus.PENDING_CONFIRMATION]):
                self.store.update_trade(t.id, status=TradeStatus.CANCELLED, note="cancelled by kill switch")
                self.store.update_signal_outcome(
                    t.signal_id,
                    accepted=False,
                    reason_code="KILL_SWITCH",
                    reason="kill switch",
                    trade_id=t.id,
                )
            try:
                report["cancelled_orders"] = self.broker.cancel_all_open_orders()
            except BrokerError as exc:
                report["errors"].append(f"cancel: {exc}")
            fills: dict[str, float] = {}
            try:
                for pos, r in self.broker.flatten_all():
                    report["flatten_orders"].append({"tradingsymbol": pos.tradingsymbol, **r.model_dump()})
                    if r.average_price:
                        fills[pos.tradingsymbol] = r.average_price
            except (BrokerError, InstrumentRejected) as exc:
                report["errors"].append(f"flatten: {exc}")
            open_trades = self.store.list_trades([TradeStatus.OPEN])
            ltps = self._ltp_for([t.tradingsymbol for t in open_trades])
            for t in open_trades:
                price = fills.get(t.tradingsymbol) or ltps.get(t.tradingsymbol) or t.fill_price or t.entry_price
                closed = self._finalize_close(t, price, ExitReason.KILL_SWITCH, exit_order_id=None)
                report["closed_trades"].append(closed.id)
            report["risk"] = self._state.to_dict()
            return report

    # ------------------------------------------------------------------ signals

    def submit_signal(self, sig: SignalIn, actor: str = "analyzer") -> SignalRecord:
        """Validate, run the governor and (in paper mode) execute. Never raises for governor blocks."""
        self.refresh()
        with self._lock:
            now = self.clock.now()
            # Hard rule: NFO options only. This raises before anything is stored or sent.
            inst = validate_option(sig.tradingsymbol, sig.exchange)
            self._validate_levels(sig)
            if sig.direction == Direction.SELL and not self.config.allow_option_writing:
                raise InstrumentRejected(
                    "option writing (SELL to open) is disabled; set DESK_ALLOW_OPTION_WRITING=true"
                )
            lots = sig.lots or self.config.default_lots
            if lots > self.config.max_lots:
                raise InstrumentRejected(f"lots {lots} exceeds DESK_MAX_LOTS={self.config.max_lots}")

            eligibility, elig_reason = self.registry.status_for_signal(sig.strategy_id, sig.code_hash, now)
            quality = self._quality(sig)

            if self.config.market_hours_only and not is_market_open(now):
                return self._reject(
                    sig, now, "MARKET_CLOSED", "outside NSE market hours (09:15-15:30 IST)", eligibility
                )

            decision = evaluate_signal(
                self._state,
                self.limits,
                quality,
                strategy_eligible=eligibility == EligibilityStatus.ELIGIBLE,
                now=now,
            )
            if decision.events or decision.state != self._state:
                self._apply(Transition(decision.state, decision.events))
            if not decision.allowed:
                reason = decision.reason
                if decision.reason_code == "STRATEGY_NOT_ELIGIBLE":
                    reason = f"{reason}: {elig_reason}"
                return self._reject(sig, now, decision.reason_code, reason, eligibility)

            record = self.store.insert_signal(
                sig,
                now=now,
                accepted=True,
                tier=decision.tier,
                reason_code=decision.reason_code,
                reason=decision.reason,
                eligibility=eligibility,
            )
            quantity = lots * self._lot_size(inst.tradingsymbol, inst.underlying)
            trade_fields = dict(
                signal_id=record.id,
                strategy_id=sig.strategy_id,
                tradingsymbol=inst.tradingsymbol,
                underlying=inst.underlying,
                direction=sig.direction,
                lots=lots,
                quantity=quantity,
                tier=decision.tier,
                mode=self.mode,
                entry_price=sig.entry,
                stop_loss=sig.stop_loss,
                target=sig.target,
                created_at=now,
                note=sig.note,
            )
            if self.mode == "live":
                deadline = now + timedelta(seconds=self.config.live_confirm_ttl_sec)
                trade = self.store.insert_trade(
                    {**trade_fields, "status": TradeStatus.PENDING_CONFIRMATION, "confirm_deadline": deadline}
                )
                self.store.update_signal_outcome(
                    record.id,
                    accepted=True,
                    reason_code="PENDING_LIVE_CONFIRMATION",
                    reason=f"{decision.reason}; awaiting operator confirmation until {deadline.isoformat()}",
                    trade_id=trade.id,
                )
                return record.model_copy(update={"trade_id": trade.id, "reason_code": "PENDING_LIVE_CONFIRMATION"})

            trade = self.store.insert_trade({**trade_fields, "status": TradeStatus.REJECTED})
            trade = self._execute_entry(trade, sig, decision.tier)  # type: ignore[arg-type]
            self.store.update_signal_outcome(
                record.id,
                accepted=trade.status == TradeStatus.OPEN,
                reason_code=decision.reason_code if trade.status == TradeStatus.OPEN else "BROKER_ERROR",
                reason=decision.reason if trade.status == TradeStatus.OPEN else (trade.note or "broker error"),
                trade_id=trade.id,
            )
            return self.store.get_signal(record.id)  # type: ignore[return-value]

    def confirm_live(self, trade_id: int, phrase: str, actor: str = "operator") -> Trade:
        """Explicit per-order live confirmation. Re-runs the governor before placing."""
        self.refresh()
        with self._lock:
            trade = self.store.get_trade(trade_id)
            if not trade or trade.status != TradeStatus.PENDING_CONFIRMATION:
                raise DeskError("trade is not awaiting confirmation")
            if self.mode != "live":
                raise DeskError("desk is not in live mode")
            if phrase.strip() != self.config.confirm_phrase:
                raise DeskError("confirmation phrase does not match")
            sig_rec = self.store.get_signal(trade.signal_id)
            if sig_rec is None:
                raise DeskError("originating signal not found")
            now = self.clock.now()
            eligibility, _ = self.registry.status_for_signal(
                sig_rec.payload.strategy_id, sig_rec.payload.code_hash, now
            )
            decision = evaluate_signal(
                self._state,
                self.limits,
                self._quality(sig_rec.payload),
                strategy_eligible=eligibility == EligibilityStatus.ELIGIBLE,
                now=now,
            )
            if decision.events or decision.state != self._state:
                self._apply(Transition(decision.state, decision.events))
            if not decision.allowed:
                self.store.update_trade(trade.id, status=TradeStatus.REJECTED, note=f"governor: {decision.reason}")
                self.store.update_signal_outcome(
                    trade.signal_id,
                    accepted=False,
                    reason_code=decision.reason_code,
                    reason=decision.reason,
                    trade_id=trade.id,
                )
                raise DeskError(f"governor blocked at confirmation: {decision.reason}")
            trade = self.store.update_trade(trade.id, tier=decision.tier, note=f"live confirmed by {actor}")
            return self._execute_entry(trade, sig_rec.payload, decision.tier)  # type: ignore[arg-type]

    def cancel_pending(self, trade_id: int, actor: str = "operator") -> Trade:
        with self._lock:
            trade = self.store.get_trade(trade_id)
            if not trade or trade.status != TradeStatus.PENDING_CONFIRMATION:
                raise DeskError("trade is not awaiting confirmation")
            self.store.update_signal_outcome(
                trade.signal_id,
                accepted=False,
                reason_code="CANCELLED_BY_OPERATOR",
                reason=f"cancelled by {actor}",
                trade_id=trade.id,
            )
            return self.store.update_trade(trade.id, status=TradeStatus.CANCELLED, note=f"cancelled by {actor}")

    # ------------------------------------------------------------------ exits

    def on_prices(self, prices: dict[str, float]) -> list[Trade]:
        """Feed LTPs. Paper broker marks positions; open trades exit on SL/target."""
        self.refresh()
        with self._lock:
            prices = {k.upper(): float(v) for k, v in prices.items()}
            now = self.clock.now()
            for sym in prices:
                self._price_seen_at[sym] = now
            if isinstance(self.broker, PaperBroker):
                self.broker.set_prices(prices)
            closed = []
            for t in self.store.list_trades([TradeStatus.OPEN]):
                ltp = prices.get(t.tradingsymbol)
                if ltp is None:
                    continue
                reason = self._exit_trigger(t, ltp)
                if reason:
                    closed.append(self._exit(t, ltp, reason))
            return closed

    def poll_prices(self) -> list[Trade]:
        """Pull LTPs from the broker for open trades (useful in live mode without a host tick feed)."""
        symbols = [t.tradingsymbol for t in self.store.list_trades([TradeStatus.OPEN])]
        if not symbols:
            return []
        return self.on_prices(self._ltp_for(symbols))

    def close_trade(self, trade_id: int, price: float | None = None, actor: str = "operator") -> Trade:
        self.refresh()
        with self._lock:
            t = self.store.get_trade(trade_id)
            if not t or t.status != TradeStatus.OPEN:
                raise DeskError("trade is not open")
            ltp = price or self._ltp_for([t.tradingsymbol]).get(t.tradingsymbol) or t.fill_price or t.entry_price
            return self._exit(t, ltp, ExitReason.MANUAL)

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _validate_levels(sig: SignalIn) -> None:
        if sig.direction == Direction.BUY and not (sig.stop_loss < sig.entry < sig.target):
            raise InstrumentRejected("for BUY signals stop_loss < entry < target is required")
        if sig.direction == Direction.SELL and not (sig.target < sig.entry < sig.stop_loss):
            raise InstrumentRejected("for SELL signals target < entry < stop_loss is required")

    def _lot_size(self, tradingsymbol: str, underlying: str) -> int:
        try:
            broker_lot = self.broker.lot_size(tradingsymbol)
        except Exception as exc:  # pragma: no cover
            log.warning("lot_size lookup failed: %s", exc)
            broker_lot = None
        return broker_lot or self.config.lot_size_for(underlying)

    def _quality(self, sig: SignalIn) -> SignalQuality:
        pct = sig.stats.confidence_percentile
        if pct is None:
            history = self.store.recent_confidences(sig.strategy_id)
            if len(history) >= self.limits.sure_shot.min_sample_trades:
                pct = sum(1 for c in history if c <= sig.confidence) / len(history)
        return SignalQuality(
            live_win_rate=sig.stats.live_win_rate,
            live_trades=sig.stats.live_trades,
            oos_sharpe=sig.stats.oos_sharpe,
            confidence_percentile=pct,
        )

    def _reject(
        self, sig: SignalIn, now: datetime, code: str, reason: str, eligibility: EligibilityStatus
    ) -> SignalRecord:
        log.info("signal rejected %s %s: %s", sig.strategy_id, sig.tradingsymbol, reason)
        return self.store.insert_signal(
            sig, now=now, accepted=False, tier=None, reason_code=code, reason=reason, eligibility=eligibility
        )

    def _execute_entry(self, trade: Trade, sig: SignalIn, tier: Tier) -> Trade:
        req = OrderRequest(
            tradingsymbol=trade.tradingsymbol,
            exchange="NFO",
            transaction_type=trade.direction,
            quantity=trade.quantity,
            order_type=self.config.entry_order_type,
            price=sig.entry if self.config.entry_order_type == "LIMIT" else None,
            product=self.config.product,
            tag=f"desk{trade.id}",
        )
        if isinstance(self.broker, PaperBroker) and not self._fresh_ltp(trade.tradingsymbol):
            # No fresh tick for this symbol: fill at the signal's entry price.
            self.broker.set_price(trade.tradingsymbol, sig.entry)
        try:
            result = self.broker.place_order(req)
        except (BrokerError, InstrumentRejected) as exc:
            log.error("entry order failed for trade %s: %s", trade.id, exc)
            return self.store.update_trade(trade.id, status=TradeStatus.REJECTED, note=f"broker error: {exc}")
        if result.status == "REJECTED":
            return self.store.update_trade(
                trade.id,
                status=TradeStatus.REJECTED,
                entry_order_id=result.order_id,
                note=f"broker rejected: {result.message}",
            )
        now = self.clock.now()
        trade = self.store.update_trade(
            trade.id,
            status=TradeStatus.OPEN,
            entry_order_id=result.order_id,
            fill_price=result.average_price or sig.entry,
            opened_at=now,
            tier=tier,
        )
        self._apply(record_trade_opened(self._state, self.limits, trade_id=trade.id, signal_id=trade.signal_id))
        return trade

    @staticmethod
    def _exit_trigger(t: Trade, ltp: float) -> ExitReason | None:
        if t.direction == Direction.BUY:
            if ltp <= t.stop_loss:
                return ExitReason.STOP_LOSS
            if ltp >= t.target:
                return ExitReason.TARGET
        else:
            if ltp >= t.stop_loss:
                return ExitReason.STOP_LOSS
            if ltp <= t.target:
                return ExitReason.TARGET
        return None

    def _exit(self, t: Trade, ltp: float, reason: ExitReason) -> Trade:
        side = Direction.SELL if t.direction == Direction.BUY else Direction.BUY
        req = OrderRequest(
            tradingsymbol=t.tradingsymbol,
            exchange="NFO",
            transaction_type=side,
            quantity=t.quantity,
            order_type="MARKET",
            product=self.config.product,
            tag=f"desk{t.id}x",
        )
        exit_price = ltp
        exit_order_id = None
        try:
            if isinstance(self.broker, PaperBroker):
                self.broker.set_price(t.tradingsymbol, ltp)
            result = self.broker.place_order(req)
            exit_order_id = result.order_id
            exit_price = result.average_price or ltp
        except BrokerError as exc:
            log.error("exit order failed for trade %s: %s (recording exit at ltp)", t.id, exc)
        return self._finalize_close(t, exit_price, reason, exit_order_id=exit_order_id)

    def _finalize_close(self, t: Trade, exit_price: float, reason: ExitReason, *, exit_order_id: str | None) -> Trade:
        fill = t.fill_price or t.entry_price
        sign = 1 if t.direction == Direction.BUY else -1
        pnl = round((exit_price - fill) * t.quantity * sign, 2)
        now = self.clock.now()
        trade = self.store.update_trade(
            t.id,
            status=TradeStatus.CLOSED,
            exit_price=exit_price,
            exit_reason=reason,
            realized_pnl=pnl,
            exit_order_id=exit_order_id,
            closed_at=now,
        )
        self._apply(record_trade_closed(self._state, self.limits, pnl, trade_id=t.id))
        return trade

    def _fresh_ltp(self, tradingsymbol: str) -> bool:
        seen = self._price_seen_at.get(tradingsymbol)
        if seen is None:
            return False
        return (self.clock.now() - seen).total_seconds() <= self.config.paper_ltp_stale_sec

    def _ltp_for(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        try:
            return self.broker.ltp(symbols)
        except BrokerError as exc:
            log.warning("ltp unavailable: %s", exc)
            return {}


def build_engine(config: DeskConfig | None = None, clock: Clock | None = None) -> DeskEngine:
    """Factory: paper broker unless ``ALLOW_LIVE_ORDERS=true`` and Kite credentials are present."""
    cfg = config or DeskConfig()
    store = DeskStore(cfg.db_path)
    broker: BrokerAdapter
    if cfg.allow_live_orders:
        if not (cfg.kite_api_key and cfg.kite_access_token):
            raise DeskError("ALLOW_LIVE_ORDERS=true requires KITE_API_KEY and KITE_ACCESS_TOKEN")
        from optionsdesk.brokers.kite import KiteBroker

        broker = KiteBroker(cfg.kite_api_key, cfg.kite_access_token)
        log.warning("LIVE ORDERS ENABLED — every order still needs explicit operator confirmation")
    else:
        broker = PaperBroker()
    return DeskEngine(cfg, store, broker, clock)
