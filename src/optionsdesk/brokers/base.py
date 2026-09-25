"""Broker adapter interface shared by the paper engine and the Kite Connect adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod

from optionsdesk.instruments import validate_option
from optionsdesk.models import OrderRequest, OrderResult, Position


class BrokerError(RuntimeError):
    pass


class BrokerAdapter(ABC):
    name: str = "abstract"
    is_live: bool = False

    def place_order(self, req: OrderRequest) -> OrderResult:
        """Validate the instrument (NFO options only) and then delegate to :meth:`_place`."""
        validate_option(req.tradingsymbol, req.exchange)
        if req.quantity <= 0:
            raise BrokerError("quantity must be positive")
        return self._place(req)

    @abstractmethod
    def _place(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None: ...

    @abstractmethod
    def open_orders(self) -> list[dict]: ...

    @abstractmethod
    def positions(self) -> list[Position]: ...

    @abstractmethod
    def ltp(self, tradingsymbols: list[str]) -> dict[str, float]: ...

    def lot_size(self, tradingsymbol: str) -> int | None:
        """Lot size if the broker knows it (Kite instruments dump); ``None`` to fall back to config."""
        return None

    def cancel_all_open_orders(self) -> list[str]:
        cancelled = []
        for o in self.open_orders():
            oid = str(o.get("order_id"))
            self.cancel_order(oid)
            cancelled.append(oid)
        return cancelled

    def flatten_all(self, tag: str = "desk-kill") -> list[tuple[Position, OrderResult]]:
        """Square off every open NFO option position with an opposite MARKET order."""
        from optionsdesk.models import Direction

        results = []
        for p in self.positions():
            if p.quantity == 0 or p.exchange != "NFO":
                continue
            side = Direction.SELL if p.quantity > 0 else Direction.BUY
            result = self.place_order(
                OrderRequest(
                    tradingsymbol=p.tradingsymbol,
                    exchange=p.exchange,
                    transaction_type=side,
                    quantity=abs(p.quantity),
                    order_type="MARKET",
                    product=p.product,
                    tag=tag,
                )
            )
            results.append((p, result))
        return results
