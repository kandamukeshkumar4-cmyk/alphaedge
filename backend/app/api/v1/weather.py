"""Weather edge desk API: NWS forecasts priced against Kalshi daily-high ladders.

Read-only, informational edges only — never touches the order path. Cached
in-process (forecasts refresh hourly at most; Kalshi weather books move slowly).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.services.weather_desk import WeatherDeskService

router = APIRouter(prefix="/api/v1", tags=["weather"])
logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 600
_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = asyncio.Lock()


@router.get("/weather/edges")
async def weather_edges(target_date: str | None = Query(default=None, alias="date")):
    """Gaussian-bucket model probabilities vs live Kalshi prices per city.

    Defaults to tomorrow (today's daily-high books close overnight)."""
    if target_date is None:
        day = (datetime.now(UTC) + timedelta(days=1)).date()
    else:
        try:
            day = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError as error:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from error

    key = day.isoformat()
    now = time.monotonic()
    async with _lock:
        cached = _cache.get(key)
        if cached is not None and now - cached[0] < _CACHE_TTL_SEC:
            return {"date": key, "cities": cached[1], "cached": True}

    # R02: a slow/failing NWS or Kalshi upstream must degrade this PUBLIC GET to
    # an honest-empty city list, never a 5xx. WeatherDeskService.scan already
    # isolates per-city failures; this guards an unexpected top-level raise (and
    # the service construction). A failed fetch is NOT cached, so the next call
    # retries rather than blanking the desk for the full TTL.
    failed = False
    try:
        service = WeatherDeskService()
        cities = await asyncio.to_thread(service.scan, day)
    except Exception:  # noqa: BLE001 - honest-empty degrade, never 5xx
        logger.warning("Weather edges upstream fetch failed for %s", key, exc_info=True)
        cities = []
        failed = True
    if not failed:
        async with _lock:
            _cache[key] = (time.monotonic(), cities)
    return {"date": key, "cities": cities, "cached": False}
