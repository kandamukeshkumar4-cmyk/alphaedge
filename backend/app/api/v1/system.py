"""System observability endpoints.

GET /api/v1/system/loops — the permanent cure for "is anything actually
running?" doubts. Returns the ``background_loop_plan`` (which loops the app
intended to start given settings) plus a per-loop last-heartbeat row sourced
from the in-process registry in app.observability.loop_state.

Public + read-only: no admin key, no orders, no DB writes. A loop that has
never recorded a heartbeat surfaces ``status="never"`` honestly.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings
from app.data.streams.runner import background_loop_plan
from app.observability.loop_state import LOOP_INTERVALS, snapshot

router = APIRouter(prefix="/api/v1/system", tags=["system"])

# Every loop the lifespan can start, in addition to the data-stream plan, so the
# endpoint answers "is the scheduler alive?" even when WS streams are off.
_ALL_LOOPS: tuple[str, ...] = (
    "price_feed",
    "live_ingest",
    "live_tick",
    "eval",
    "kalshi_ws",
    "polymarket_ws",
    "news_scan",
    "weather_scan",
    "morning_research",
    "whale_refresh",
    "wc2026_resolve",
)


@router.get("/loops")
async def get_loops() -> dict[str, Any]:
    settings = get_settings()
    plan = background_loop_plan(settings)
    beats = snapshot()

    loops: list[dict[str, Any]] = []
    for name in _ALL_LOOPS:
        hb = beats.get(name)
        interval = LOOP_INTERVALS.get(name)
        loops.append(
            {
                "name": name,
                "planned": name in plan,
                "running": hb is not None,
                "status": hb["status"] if hb else "never",
                "last_heartbeat": hb["last_heartbeat_iso"] if hb else None,
                "interval_sec": interval,
                "detail": hb["detail"] if hb else None,
            }
        )

    return {
        "plan": plan,
        "loops": loops,
        "paper_trading_only": settings.paper_trading_only,
    }
