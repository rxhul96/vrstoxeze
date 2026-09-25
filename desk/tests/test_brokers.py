from __future__ import annotations

import pytest

from optionsdesk.brokers.base import BrokerError
from optionsdesk.brokers.kite import KiteBroker
from optionsdesk.brokers.paper import PaperBroker
from optionsdesk.instruments import InstrumentRejected
from optionsdesk.models import Direction, OrderRequest

SYM = "NIFTY24SEP25000CE"


def _req(**kw) -> OrderRequest:
    base = dict(tradingsymbol=SYM, exchange="NFO", transaction_type=Direction.BUY, quantity=75)
    base.update(kw)
    return OrderRequest(**base)


# ------------------------------------------------------------------------------------------
# paper
# ------------------------------------------------------------------------------------------


def test_paper_requires_a_price():
    b = PaperBroker()
    with pytest.raises(BrokerError, match="no price"):
        b.place_order(_req())


def test_paper_fills_and_tracks_positions():
    b = PaperBroker()
    b.set_price(SYM, 100.0)
    r = b.place_order(_req())
    assert r.status == "COMPLETE" and r.average_price == 100.0 and r.filled_quantity == 75
    (pos,) = b.positions()
    assert pos.quantity == 75 and pos.average_price == 100.0
    b.set_price(SYM, 110.0)
    assert b.positions()[0].pnl == 750.0
    b.place_order(_req(transaction_type=Direction.SELL))
    assert b.positions() == []
    assert b.ltp([SYM]) == {SYM: 110.0}


def test_paper_averages_when_adding():
    b = PaperBroker()
    b.set_price(SYM, 100.0)
    b.place_order(_req())
    b.set_price(SYM, 120.0)
    b.place_order(_req())
    (pos,) = b.positions()
    assert pos.quantity == 150 and pos.average_price == 110.0


def test_paper_flatten_all_squares_off():
    b = PaperBroker()
    b.set_price(SYM, 100.0)
    b.place_order(_req())
    b.set_price("BANKNIFTY24SEP52000PE", 300.0)
    b.place_order(_req(tradingsymbol="BANKNIFTY24SEP52000PE", quantity=30))
    results = b.flatten_all()
    assert len(results) == 2 and b.positions() == []
    assert {p.tradingsymbol for p, _ in results} == {SYM, "BANKNIFTY24SEP52000PE"}


@pytest.mark.parametrize(
    "req",
    [
        dict(tradingsymbol="RELIANCE", exchange="NSE"),
        dict(tradingsymbol="NIFTY24SEPFUT", exchange="NFO"),
        dict(tradingsymbol=SYM, exchange="BFO"),
        dict(tradingsymbol="SENSEX24SEP80000CE", exchange="BFO"),
    ],
)
def test_every_broker_rejects_non_nfo_options(req):
    b = PaperBroker()
    b.set_price(req["tradingsymbol"], 100.0)
    with pytest.raises(InstrumentRejected):
        b.place_order(_req(**req))
    assert b.positions() == []


# ------------------------------------------------------------------------------------------
# kite (fake client)
# ------------------------------------------------------------------------------------------


class FakeKite:
    VARIETY_REGULAR = "regular"
    EXCHANGE_NFO = "NFO"
    VALIDITY_DAY = "DAY"

    def __init__(self):
        self.placed = []
        self.cancelled = []
        self._orders = []
        self._positions = {"net": []}

    def place_order(self, **kw):
        self.placed.append(kw)
        return f"K{len(self.placed)}"

    def order_history(self, oid):
        return [{"status": "COMPLETE", "filled_quantity": 75, "average_price": 101.5, "status_message": None}]

    def cancel_order(self, variety, order_id):
        self.cancelled.append(order_id)

    def orders(self):
        return self._orders

    def positions(self):
        return self._positions

    def ltp(self, keys):
        return {k: {"last_price": 99.0} for k in keys}

    def instruments(self, exchange):
        return [{"tradingsymbol": SYM, "lot_size": 75, "instrument_type": "CE"}]


def test_kite_places_only_nfo_regular_day_orders():
    fake = FakeKite()
    b = KiteBroker("key", "token", client=fake)
    r = b.place_order(_req(tag="desk1"))
    assert r.order_id == "K1" and r.status == "COMPLETE" and r.average_price == 101.5
    (kw,) = fake.placed
    assert kw["exchange"] == "NFO" and kw["variety"] == "regular" and kw["validity"] == "DAY"
    assert kw["tradingsymbol"] == SYM and kw["transaction_type"] == "BUY" and kw["quantity"] == 75
    assert "price" not in kw


def test_kite_refuses_non_option_before_touching_client():
    fake = FakeKite()
    b = KiteBroker("key", "token", client=fake)
    with pytest.raises(InstrumentRejected):
        b.place_order(_req(tradingsymbol="NIFTY24SEPFUT"))
    with pytest.raises(InstrumentRejected):
        b.place_order(_req(exchange="NSE"))
    assert fake.placed == []


def test_kite_limit_requires_price():
    b = KiteBroker("key", "token", client=FakeKite())
    with pytest.raises(BrokerError, match="LIMIT"):
        b.place_order(_req(order_type="LIMIT"))


def test_kite_cancel_positions_ltp_and_lot_size():
    fake = FakeKite()
    fake._orders = [
        {"order_id": "K9", "status": "OPEN", "exchange": "NFO"},
        {"order_id": "K10", "status": "COMPLETE", "exchange": "NFO"},
        {"order_id": "K11", "status": "OPEN", "exchange": "NSE"},
    ]
    fake._positions = {
        "net": [
            {
                "tradingsymbol": SYM,
                "exchange": "NFO",
                "quantity": 75,
                "average_price": 100,
                "last_price": 99,
                "pnl": -75,
                "product": "MIS",
            },
            {"tradingsymbol": "RELIANCE", "exchange": "NSE", "quantity": 10, "average_price": 3000},
        ]
    }
    b = KiteBroker("key", "token", client=fake)
    assert b.cancel_all_open_orders() == ["K9"]  # only open NFO orders
    (pos,) = b.positions()
    assert pos.tradingsymbol == SYM and pos.quantity == 75
    assert b.ltp([SYM]) == {SYM: 99.0}
    assert b.lot_size(SYM) == 75 and b.lot_size("BANKNIFTY24SEP52000PE") is None
    flat = b.flatten_all()
    assert len(flat) == 1 and fake.placed[-1]["transaction_type"] == "SELL" and fake.placed[-1]["quantity"] == 75
