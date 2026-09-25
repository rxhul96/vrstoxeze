"""Paper broker: same interface as Kite, fills instantly at the last known price."""

from __future__ import annotations

import itertools
import threading

from optionsdesk.brokers.base import BrokerAdapter, BrokerError
from optionsdesk.models import Direction, OrderRequest, OrderResult, Position


class PaperBroker(BrokerAdapter):
    name = "paper"
    is_live = False

    def __init__(self, slippage_pct: float = 0.0) -> None:
        self._prices: dict[str, float] = {}
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, dict] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self.slippage_pct = slippage_pct

    # -- price feed ---------------------------------------------------------------------------
    def set_price(self, tradingsymbol: str, price: float) -> None:
        with self._lock:
            self._prices[tradingsymbol.upper()] = float(price)
            pos = self._positions.get(tradingsymbol.upper())
            if pos:
                pos.last_price = float(price)
                pos.pnl = round((float(price) - pos.average_price) * pos.quantity, 2)

    def set_prices(self, prices: dict[str, float]) -> None:
        for k, v in prices.items():
            self.set_price(k, v)

    def ltp(self, tradingsymbols: list[str]) -> dict[str, float]:
        with self._lock:
            return {s: self._prices[s.upper()] for s in tradingsymbols if s.upper() in self._prices}

    # -- orders -------------------------------------------------------------------------------
    def _place(self, req: OrderRequest) -> OrderResult:
        with self._lock:
            sym = req.tradingsymbol.upper()
            price = req.price if req.order_type == "LIMIT" and req.price else self._prices.get(sym)
            if price is None:
                raise BrokerError(f"paper broker has no price for {sym}; push an LTP first or use a LIMIT price")
            slip = price * self.slippage_pct / 100.0
            fill = price + slip if req.transaction_type == Direction.BUY else price - slip
            order_id = f"P{next(self._ids):06d}"
            signed = req.quantity if req.transaction_type == Direction.BUY else -req.quantity
            pos = self._positions.get(sym)
            if pos is None or pos.quantity == 0:
                self._positions[sym] = Position(
                    tradingsymbol=sym,
                    exchange="NFO",
                    quantity=signed,
                    average_price=fill,
                    last_price=price,
                    pnl=0.0,
                    product=req.product,
                )
            else:
                new_qty = pos.quantity + signed
                if (pos.quantity > 0) == (signed > 0):  # adding to position
                    total_cost = pos.average_price * abs(pos.quantity) + fill * abs(signed)
                    pos.average_price = total_cost / abs(new_qty)
                pos.quantity = new_qty
                pos.last_price = price
                pos.pnl = round((price - pos.average_price) * pos.quantity, 2) if new_qty else 0.0
                if new_qty == 0:
                    del self._positions[sym]
            self._orders[order_id] = {
                "order_id": order_id,
                "tradingsymbol": sym,
                "status": "COMPLETE",
                "transaction_type": req.transaction_type.value,
                "quantity": req.quantity,
                "average_price": fill,
                "tag": req.tag,
            }
            return OrderResult(
                order_id=order_id,
                status="COMPLETE",
                filled_quantity=req.quantity,
                average_price=round(fill, 2),
                message="paper fill",
            )

    def cancel_order(self, order_id: str) -> None:
        with self._lock:
            o = self._orders.get(order_id)
            if o and o["status"] == "OPEN":
                o["status"] = "CANCELLED"

    def open_orders(self) -> list[dict]:
        with self._lock:
            return [o for o in self._orders.values() if o["status"] == "OPEN"]

    def positions(self) -> list[Position]:
        with self._lock:
            return [p.model_copy() for p in self._positions.values()]
