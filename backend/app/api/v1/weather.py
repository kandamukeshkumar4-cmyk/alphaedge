"""Weather edge desk API: NWS forecasts priced against Kalshi daily-high ladders.

Read-only, informational edges only — never touches the order path. Cached
in-process (forecasts refresh hourly at most; Kalshi weather books move slowly).
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.services.weather_desk import WeatherDeskService

router = APIRouter(prefix="/api/v1", tags=["weather"])

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

    service = WeatherDeskService()
    cities = await asyncio.to_thread(service.scan, day)
    async with _lock:
        _cache[key] = (time.monotonic(), cities)
    return {"date": key, "cities": cities, "cached": False}
