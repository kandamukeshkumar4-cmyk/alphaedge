import asyncio
import random
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])

PRICE_MIN = 0.01
PRICE_MAX = 0.99
DRIFT_MAX = 0.005
BROADCAST_INTERVAL_SEC = 2.0


def _clamp_price(value: float) -> float:
    return max(PRICE_MIN, min(PRICE_MAX, value))


def _drift_price(value: float) -> float:
    delta = random.uniform(-DRIFT_MAX, DRIFT_MAX)
    return round(_clamp_price(value + delta), 4)


@router.websocket("/prices")
async def prices_feed(websocket: WebSocket, market: str = Query(..., min_length=1)):
    settings = get_settings()
    if not settings.paper_trading_only:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    slug = market
    yes = _clamp_price(0.62 + random.uniform(-0.05, 0.05))
    no = round(_clamp_price(1.0 - yes), 4)

    try:
        while True:
            await websocket.send_json(
                {
                    "slug": slug,
                    "yes": yes,
                    "no": no,
                    "ts": int(time.time()),
                }
            )
            await asyncio.sleep(BROADCAST_INTERVAL_SEC)
            yes = _drift_price(yes)
            no = round(_clamp_price(1.0 - yes), 4)
    except WebSocketDisconnect:
        pass
