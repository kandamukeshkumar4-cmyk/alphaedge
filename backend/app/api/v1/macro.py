"""Macro desk API (E11): headline economic indicators (FRED / World Bank).

Read-only, no auth. Cached in-process for a day (macro series update at most
daily) so we don't hammer the upstream APIs on every page load.
"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.data.connectors.fred import FredConnector, MacroIndicator

router = APIRouter(prefix="/api/v1", tags=["macro"])

_CACHE_TTL_SEC = 6 * 3600  # macro data moves slowly; refresh at most 4x/day


class MacroIndicatorOut(BaseModel):
    key: str
    label: str
    unit: str
    value: float
    prev_value: float | None
    change: float | None
    date: str
    source: str


class MacroOut(BaseModel):
    indicators: list[MacroIndicatorOut]
    source: str  # "fred" | "worldbank" | "none"
    updated_at: int


_cache: dict[str, object] = {"at": 0.0, "data": None}
_lock = asyncio.Lock()


def _to_out(ind: MacroIndicator) -> MacroIndicatorOut:
    return MacroIndicatorOut(
        key=ind.key, label=ind.label, unit=ind.unit, value=ind.value,
        prev_value=ind.prev_value, change=ind.change, date=ind.date, source=ind.source,
    )


def _build(connector: FredConnector) -> MacroOut:
    indicators = connector.fetch_indicators()
    source = indicators[0].source if indicators else "none"
    return MacroOut(
        indicators=[_to_out(i) for i in indicators],
        source=source,
        updated_at=int(time.time()),
    )


@router.get("/macro", response_model=MacroOut)
async def macro_dashboard() -> MacroOut:
    now = time.time()
    cached = _cache.get("data")
    if cached is not None and now - float(_cache.get("at", 0.0)) < _CACHE_TTL_SEC:
        return cached  # type: ignore[return-value]

    async with _lock:
        cached = _cache.get("data")
        if cached is not None and time.time() - float(_cache.get("at", 0.0)) < _CACHE_TTL_SEC:
            return cached  # type: ignore[return-value]
        settings = get_settings()
        connector = FredConnector(api_key=settings.fred_api_key)
        # The connector uses blocking httpx; run off the event loop.
        result = await asyncio.to_thread(_build, connector)
        # Never cache an empty/failed fetch for the full TTL — a transient
        # upstream blip would otherwise blank the dashboard for 6h. Only a
        # successful, non-empty result is cached; empties are retried next call.
        if result.indicators:
            _cache["data"] = result
            _cache["at"] = time.time()
        return result
