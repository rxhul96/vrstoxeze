"""Single in-process market data bus. One Kite connection fans out here."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Awaitable

Subscribers = list[Callable[[dict], Awaitable[None] | None]]


class MarketBus:
    def __init__(self) -> None:
        self._subs: Subscribers = []
        self.snapshot: dict[str, Any] = {}
        self.last_ts: float = 0.0
        self.kite_connections: int = 0

    def subscribe(self, fn: Callable[[dict], Awaitable[None] | None]) -> None:
        self._subs.append(fn)

    async def publish(self, snapshot: dict) -> None:
        snapshot = dict(snapshot)
        snapshot.setdefault("bus_ts", time.time())
        self.snapshot = snapshot
        self.last_ts = snapshot["bus_ts"]
        for fn in list(self._subs):
            result = fn(snapshot)
            if asyncio.iscoroutine(result):
                await result

    def register_kite_connection(self) -> None:
        # Exactly one KiteTicker for the process. Reloads/tests are no-ops.
        if self.kite_connections >= 1:
            return
        self.kite_connections = 1
