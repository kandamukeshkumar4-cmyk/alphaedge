from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.broadcast import hub
from app.core.config import get_settings
from app.db.models import OddsSnapshot
from app.db.session import get_db
from app.services.market_service import CATALOG_SLUGS

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])

_QUEUE_TIMEOUT_SEC = 29.0


@router.websocket("/prices")
async def prices_feed(
    websocket: WebSocket,
    market: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> None:
    settings = get_settings()
    if not settings.paper_trading_only:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    slug = market
    if slug not in CATALOG_SLUGS:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    result = await db.execute(
        select(OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    row = result.first()
    if row is not None:
        yes = float(row[0])
    else:
        yes = 0.5
    no = round(1.0 - yes, 4)

    await websocket.send_json({"slug": slug, "yes": yes, "no": no, "ts": int(time.time())})

    q = hub.subscribe(slug)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=_QUEUE_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                continue
            yes = payload.get("yes", yes)
            no = payload.get("no", no)
            try:
                await websocket.send_json(payload)
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(slug, q)
