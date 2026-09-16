"""Reconnect / single-bus invariants."""
import asyncio

from backend.feed.bus import MarketBus


def test_single_kite_connection():
    bus = MarketBus()
    bus.register_kite_connection()
    bus.register_kite_connection()
    assert bus.kite_connections == 1


def test_bus_fans_out_once():
    bus = MarketBus()
    seen = []

    async def sub(s):
        seen.append(s["n"])

    bus.subscribe(sub)

    async def run():
        await bus.publish({"n": 1})
        await bus.publish({"n": 2})

    asyncio.run(run())
    assert seen == [1, 2]
    assert bus.snapshot["n"] == 2
