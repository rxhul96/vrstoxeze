"""FastAPI router for the desk. Mount with ``app.include_router(build_desk_router(engine))``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from optionsdesk.brokers.base import BrokerError
from optionsdesk.engine import DeskEngine, DeskError
from optionsdesk.instruments import InstrumentRejected
from optionsdesk.models import SignalIn, StrategyRegistration, TradeStatus


class ActorBody(BaseModel):
    actor: str = Field(default="operator", max_length=64)


class ArmBody(ActorBody):
    confirm: bool = Field(description="must be true; the UI asks the operator to tick a box")


class KillBody(ActorBody):
    reason: str = Field(default="kill switch", max_length=200)


class PhraseBody(ActorBody):
    phrase: str = Field(max_length=200)
    note: str = Field(default="", max_length=300)


class CloseBody(ActorBody):
    price: float | None = Field(default=None, gt=0)


class PricesBody(BaseModel):
    prices: dict[str, float] = Field(description="tradingsymbol -> LTP")


def build_desk_router(engine: DeskEngine, *, prefix: str = "/desk", api_token: str | None = None) -> APIRouter:
    token = api_token if api_token is not None else engine.config.api_token

    async def require_token(x_desk_token: str | None = Header(default=None)) -> None:
        if token and x_desk_token != token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid X-Desk-Token")

    router = APIRouter(prefix=prefix, tags=["desk"], dependencies=[Depends(require_token)])

    def _desk_error(exc: Exception) -> HTTPException:
        if isinstance(exc, InstrumentRejected):
            # Literal 422: starlette < 0.45 (pinned by the analyzer) lacks HTTP_422_UNPROCESSABLE_CONTENT.
            return HTTPException(422, str(exc))
        if isinstance(exc, DeskError):
            return HTTPException(status.HTTP_409_CONFLICT, str(exc))
        if isinstance(exc, BrokerError):
            return HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
        raise exc

    # ---------------------------------------------------------------- status & controls

    @router.get("/status")
    def get_status() -> dict[str, Any]:
        return engine.status()

    @router.post("/arm")
    def post_arm(body: ArmBody) -> dict[str, Any]:
        if not body.confirm:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm must be true")
        try:
            return engine.arm(actor=body.actor).to_dict()
        except DeskError as exc:
            raise _desk_error(exc) from exc

    @router.post("/disarm")
    def post_disarm(body: ActorBody) -> dict[str, Any]:
        return engine.disarm(actor=body.actor).to_dict()

    @router.post("/kill")
    def post_kill(body: KillBody) -> dict[str, Any]:
        return engine.kill(actor=body.actor, reason=body.reason)

    @router.post("/clear-stop")
    def post_clear_stop(body: PhraseBody) -> dict[str, Any]:
        try:
            return engine.clear_stop(body.phrase, actor=body.actor, note=body.note).to_dict()
        except DeskError as exc:
            raise _desk_error(exc) from exc

    # ---------------------------------------------------------------- signals

    @router.post("/signals", status_code=status.HTTP_200_OK)
    def post_signal(sig: SignalIn) -> dict[str, Any]:
        try:
            rec = engine.submit_signal(sig)
        except (InstrumentRejected, DeskError, BrokerError) as exc:
            raise _desk_error(exc) from exc
        return rec.model_dump(mode="json")

    @router.get("/signals")
    def get_signals(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
        return [s.model_dump(mode="json") for s in engine.store.list_signals(limit=limit)]

    # ---------------------------------------------------------------- trades

    @router.get("/trades")
    def get_trades(
        status_filter: list[TradeStatus] | None = Query(default=None, alias="status"),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        engine.refresh()
        return [t.model_dump(mode="json") for t in engine.store.list_trades(status_filter, limit=limit)]

    @router.get("/trades/{trade_id}")
    def get_trade(trade_id: int) -> dict[str, Any]:
        t = engine.store.get_trade(trade_id)
        if not t:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "trade not found")
        return t.model_dump(mode="json")

    @router.post("/trades/{trade_id}/confirm")
    def post_confirm(trade_id: int, body: PhraseBody) -> dict[str, Any]:
        try:
            return engine.confirm_live(trade_id, body.phrase, actor=body.actor).model_dump(mode="json")
        except (DeskError, BrokerError) as exc:
            raise _desk_error(exc) from exc

    @router.post("/trades/{trade_id}/cancel")
    def post_cancel(trade_id: int, body: ActorBody) -> dict[str, Any]:
        try:
            return engine.cancel_pending(trade_id, actor=body.actor).model_dump(mode="json")
        except DeskError as exc:
            raise _desk_error(exc) from exc

    @router.post("/trades/{trade_id}/close")
    def post_close(trade_id: int, body: CloseBody) -> dict[str, Any]:
        try:
            return engine.close_trade(trade_id, price=body.price, actor=body.actor).model_dump(mode="json")
        except (DeskError, BrokerError) as exc:
            raise _desk_error(exc) from exc

    @router.post("/prices")
    def post_prices(body: PricesBody) -> dict[str, Any]:
        closed = engine.on_prices(body.prices)
        return {"closed": [t.model_dump(mode="json") for t in closed]}

    @router.get("/positions")
    def get_positions() -> list[dict[str, Any]]:
        return [p.model_dump(mode="json") for p in engine.positions()]

    # ---------------------------------------------------------------- audit & registry

    @router.get("/risk-events")
    def get_risk_events(limit: int = Query(default=200, ge=1, le=2000)) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in engine.store.list_risk_events(limit=limit)]

    @router.get("/strategies")
    def get_strategies() -> list[dict[str, Any]]:
        return [s.model_dump(mode="json") for s in engine.registry.list(engine.clock.now())]

    @router.post("/strategies")
    def post_strategy(reg: StrategyRegistration) -> dict[str, Any]:
        return engine.registry.register(reg, engine.clock.now()).model_dump(mode="json")

    return router
