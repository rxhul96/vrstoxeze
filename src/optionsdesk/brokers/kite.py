"""Zerodha Kite Connect adapter.

Only NFO option orders can pass through here — :meth:`BrokerAdapter.place_order` validates the
instrument before ``_place`` is called, and ``_place`` re-checks the exchange as a belt-and-braces
guard against any future caller bypassing the base class.
"""

from __future__ import annotations

import logging
from typing import Any

from optionsdesk.brokers.base import BrokerAdapter, BrokerError
from optionsdesk.instruments import ALLOWED_EXCHANGE, validate_option
from optionsdesk.models import OrderRequest, OrderResult, Position

log = logging.getLogger("optionsdesk.kite")

_OPEN_STATUSES = {
    "OPEN",
    "TRIGGER PENDING",
    "AMO REQ RECEIVED",
    "OPEN PENDING",
    "MODIFY PENDING",
    "PUT ORDER REQ RECEIVED",
}


class KiteBroker(BrokerAdapter):
    name = "kite"
    is_live = True

    def __init__(self, api_key: str, access_token: str, client: Any | None = None) -> None:
        if client is None:
            try:
                from kiteconnect import KiteConnect
            except ImportError as exc:  # pragma: no cover
                raise BrokerError("kiteconnect is not installed; pip install 'optionsdesk[kite]'") from exc
            client = KiteConnect(api_key=api_key)
            client.set_access_token(access_token)
        self.kite = client
        self._lot_sizes: dict[str, int] | None = None

    # -- helpers ------------------------------------------------------------------------------
    def _load_instruments(self) -> None:
        try:
            rows = self.kite.instruments(ALLOWED_EXCHANGE)
        except Exception as exc:  # network / auth
            log.warning("could not load NFO instruments: %s", exc)
            self._lot_sizes = {}
            return
        self._lot_sizes = {
            r["tradingsymbol"]: int(r["lot_size"]) for r in rows if r.get("instrument_type") in ("CE", "PE")
        }

    def lot_size(self, tradingsymbol: str) -> int | None:
        if self._lot_sizes is None:
            self._load_instruments()
        return (self._lot_sizes or {}).get(tradingsymbol.upper())

    # -- orders -------------------------------------------------------------------------------
    def _place(self, req: OrderRequest) -> OrderResult:
        inst = validate_option(req.tradingsymbol, req.exchange)
        if inst.exchange != ALLOWED_EXCHANGE:  # pragma: no cover - validate_option guarantees this
            raise BrokerError("refusing non-NFO order")
        kwargs = dict(
            variety=self.kite.VARIETY_REGULAR,
            exchange=self.kite.EXCHANGE_NFO,
            tradingsymbol=inst.tradingsymbol,
            transaction_type=req.transaction_type.value,
            quantity=int(req.quantity),
            product=req.product,
            order_type=req.order_type,
            validity=self.kite.VALIDITY_DAY,
            tag=(req.tag or "optionsdesk")[:20],
        )
        if req.order_type == "LIMIT":
            if not req.price:
                raise BrokerError("LIMIT order requires a price")
            kwargs["price"] = float(req.price)
        try:
            order_id = str(self.kite.place_order(**kwargs))
        except Exception as exc:
            raise BrokerError(f"kite place_order failed: {exc}") from exc
        return self._order_result(order_id)

    def _order_result(self, order_id: str) -> OrderResult:
        try:
            history = self.kite.order_history(order_id)
        except Exception as exc:
            log.warning("order_history(%s) failed: %s", order_id, exc)
            return OrderResult(order_id=order_id, status="OPEN", message="placed; status unknown")
        last = history[-1] if history else {}
        return OrderResult(
            order_id=order_id,
            status=str(last.get("status", "OPEN")),
            filled_quantity=int(last.get("filled_quantity") or 0),
            average_price=float(last["average_price"]) if last.get("average_price") else None,
            message=last.get("status_message"),
            raw={
                k: v for k, v in last.items() if k in ("status", "status_message", "filled_quantity", "average_price")
            },
        )

    def refresh_order(self, order_id: str) -> OrderResult:
        return self._order_result(order_id)

    def cancel_order(self, order_id: str) -> None:
        try:
            self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR, order_id=order_id)
        except Exception as exc:
            raise BrokerError(f"kite cancel_order({order_id}) failed: {exc}") from exc

    def open_orders(self) -> list[dict]:
        try:
            orders = self.kite.orders()
        except Exception as exc:
            raise BrokerError(f"kite orders() failed: {exc}") from exc
        return [o for o in orders if o.get("status") in _OPEN_STATUSES and o.get("exchange") == ALLOWED_EXCHANGE]

    def positions(self) -> list[Position]:
        try:
            data = self.kite.positions()
        except Exception as exc:
            raise BrokerError(f"kite positions() failed: {exc}") from exc
        out = []
        for p in data.get("net", []):
            if p.get("exchange") != ALLOWED_EXCHANGE:
                continue
            out.append(
                Position(
                    tradingsymbol=p["tradingsymbol"],
                    exchange=p["exchange"],
                    quantity=int(p.get("quantity") or 0),
                    average_price=float(p.get("average_price") or 0),
                    last_price=float(p["last_price"]) if p.get("last_price") is not None else None,
                    pnl=float(p["pnl"]) if p.get("pnl") is not None else None,
                    product=p.get("product", "MIS"),
                )
            )
        return out

    def ltp(self, tradingsymbols: list[str]) -> dict[str, float]:
        if not tradingsymbols:
            return {}
        keys = [f"{ALLOWED_EXCHANGE}:{s.upper()}" for s in tradingsymbols]
        try:
            data = self.kite.ltp(keys)
        except Exception as exc:
            raise BrokerError(f"kite ltp() failed: {exc}") from exc
        return {k.split(":", 1)[1]: float(v["last_price"]) for k, v in data.items()}
