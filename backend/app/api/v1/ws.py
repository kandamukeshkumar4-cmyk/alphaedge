from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.broadcast import hub
from app.core.config import get_settings
from app.core.event_bus import get_event_bus
from app.db.models import Market, OddsSnapshot
from app.db.session import AsyncSessionLocal
from app.services.market_service import CATALOG_SLUGS

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])

_QUEUE_TIMEOUT_SEC = 29.0

# Hub topics multiplexed onto the public /feed socket (briefs + alerts +
# unified feed + public paper-trade activity from Loop V15 B4 + forecast
# lifecycle events Loop V49 E1). Per-user notifications stay on authenticated
# REST endpoints and must never be subscribed here.
_FEED_TOPICS = (
    "briefs",
    "alerts",
    "feed",
    "activity",
    "forecasts",
)

# In-process event-bus topics fanned onto the same socket (Redis-free push path).
_BUS_TOPICS = (
    "market.tick",
    "signal.new",
    "order.filled",
    "order.cancelled",
    "market.resolved",
)


@router.websocket("/prices")
async def prices_feed(
    websocket: WebSocket,
    market: str = Query(..., min_length=1),
) -> None:
    """Per-market price stream via event_bus ``market.tick``.

    Must not hold a DB session for the socket lifetime. Subscribes to the
    shared in-process bus (same drop-oldest slow-subscriber throttle as
    ``/feed``) and filters frames to ``market``'s slug.
    """
    settings = get_settings()
    if not settings.paper_trading_only:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    slug = market
    yes = 0.5

    async with AsyncSessionLocal() as db:
        if slug not in CATALOG_SLUGS:
            known = await db.scalar(select(Market.id).where(Market.slug == slug).limit(1))
            if known is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        result = await db.execute(
            select(OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == slug)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        row = result.first()
        if row is not None:
            yes = float(row[0])

    await websocket.accept()
    await websocket.send_json(
        {"slug": slug, "yes_price": yes, "ts": int(time.time())}
    )

    # Reuse the process-wide bus — do NOT introduce a second global.
    bus = get_event_bus()
    sub = bus.subscribe("market.tick")
    try:
        while True:
            try:
                payload = await asyncio.wait_for(sub.get(), timeout=_QUEUE_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("slug") != slug:
                continue
            raw = payload.get("yes_price", payload.get("yes"))
            if raw is None:
                continue
            try:
                await websocket.send_json(
                    {
                        "slug": slug,
                        "yes_price": float(raw),
                        "ts": int(payload.get("ts") or time.time()),
                    }
                )
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        sub.close()


@router.websocket("/feed")
async def activity_feed(websocket: WebSocket) -> None:
    """Real-time multiplexed feed of analyst briefs (T07) + dispatched alerts (T09).

    Replaces the frontend's 30s polling of `/briefs` and `/alerts`: the analyst
    and alert dispatcher already `hub.publish("briefs"/"alerts", ...)`, so this
    just fans those topics onto one socket. Each frame is tagged with `channel`
    ("briefs" | "alerts" | "system"). Holds no DB session for the socket lifetime.
    """
    settings = get_settings()
    if not settings.paper_trading_only:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await websocket.send_json({"channel": "system", "connected": True, "ts": int(time.time())})

    queues = {topic: hub.subscribe(topic) for topic in _FEED_TOPICS}
    # In-process bus subscriptions expose the same .get() coroutine as hub queues,
    # so the two source kinds merge into one getter set below.
    bus = get_event_bus()
    bus_subs = {topic: bus.subscribe(topic) for topic in _BUS_TOPICS}
    sources = {**queues, **bus_subs}
    # One persistent getter task per topic. Only the completed getter is
    # recreated each loop, so a message that arrives on another topic between
    # iterations is never consumed-then-dropped.
    getters = {topic: asyncio.ensure_future(src.get()) for topic, src in sources.items()}
    try:
        while True:
            done, _pending = await asyncio.wait(
                getters.values(),
                timeout=_QUEUE_TIMEOUT_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                try:
                    await websocket.send_json({"channel": "system", "keepalive": True})
                    continue
                except Exception:
                    break
            for topic, task in list(getters.items()):
                if task not in done:
                    continue
                payload = task.result()
                getters[topic] = asyncio.ensure_future(sources[topic].get())
                try:
                    await websocket.send_json({"channel": topic, **payload})
                except Exception:
                    return
    except WebSocketDisconnect:
        pass
    finally:
        for task in getters.values():
            task.cancel()
        for topic, q in queues.items():
            hub.unsubscribe(topic, q)
        for sub in bus_subs.values():
            sub.close()
