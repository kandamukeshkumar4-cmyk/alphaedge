"""N03 — Edge history (Loop V9).

``GET /api/v1/markets/{slug}/edge-history?window=`` — a bounded time series of
``{t, model_p, market_p, edge}`` for ONE market, for charting the model-vs-market
edge over time. Composed READ-ONLY from the existing prediction + price logs:

* ``model_p`` — each ``PredictionLog.predicted_prob`` (the desk/M02 model source),
  in time order;
* ``market_p`` — the market-implied price at that instant: the latest
  ``OddsSnapshot.implied_yes`` at-or-before the prediction timestamp;
* ``edge`` — ``model_p − market_p`` (signed; shows which side the model leaned and
  when it flipped), ``null`` when there is no market price yet.

**PUBLIC GET.** No new pipeline, no new table, persists nothing, order path never
imported. An unknown slug returns an honest **200** ``{found:false, series:[]}``
(never a 404); a known market with no predictions returns ``{found:true,
series:[]}``. Bounded point count (``_MAX_POINTS``) and a bounded window keep the
public GET bounded. Cacheable (desk-cache TTL pattern; additive ``cached`` flag)
and served with the M03 weak-ETag / conditional-GET helper. Swept by the I01 5xx
guard (auto-covered ``{slug}`` public GET).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts_feed import _resolve_window_hours
from app.core import opportunities_cache
from app.core.config import get_settings
from app.core.http_etag import etag_json_response
from app.db.models import OddsSnapshot, PredictionLog
from app.db.session import get_db
from app.services.market_service import MarketService

router = APIRouter(prefix="/api/v1", tags=["edge-history"])
settings = get_settings()

EDGE_HISTORY_DISCLAIMER = (
    "Model-vs-market edge history — the model probability, the market-implied "
    "price and their gap over time, from existing prediction and price logs. "
    "Signal only; paper trading only — simulated funds, no execution."
)

# A public GET must never do unbounded work: cap the returned point count.
_MAX_POINTS = 200


async def _build_series(
    db: AsyncSession, slug: str, since: datetime
) -> list[dict[str, Any]]:
    """Ordered ``{t, model_p, market_p, edge}`` points from the prediction +
    price logs. ``market_p`` is the newest odds snapshot at-or-before each
    prediction instant (a two-pointer walk over ascending timestamps)."""
    predictions = (
        await db.execute(
            select(PredictionLog.predicted_at, PredictionLog.predicted_prob)
            .where(
                PredictionLog.market_slug == slug,
                PredictionLog.predicted_at >= since,
            )
            .order_by(PredictionLog.predicted_at.asc())
        )
    ).all()
    if not predictions:
        return []
    # Keep the point count bounded — retain the MOST RECENT window of points.
    if len(predictions) > _MAX_POINTS:
        predictions = predictions[-_MAX_POINTS:]

    snapshots = (
        await db.execute(
            select(OddsSnapshot.captured_at, OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == slug)
            .order_by(OddsSnapshot.captured_at.asc())
        )
    ).all()

    series: list[dict[str, Any]] = []
    idx = 0
    market_p: float | None = None
    for predicted_at, predicted_prob in predictions:
        # Advance through every snapshot at-or-before this prediction instant.
        while idx < len(snapshots) and snapshots[idx][0] <= predicted_at:
            market_p = round(float(snapshots[idx][1]), 4)
            idx += 1
        model_p = round(float(predicted_prob), 4)
        edge = round(model_p - market_p, 4) if market_p is not None else None
        series.append(
            {
                "t": predicted_at.isoformat(),
                "model_p": model_p,
                "market_p": market_p,
                "edge": edge,
            }
        )
    return series


@router.get("/markets/{slug}/edge-history")
async def get_market_edge_history(
    slug: str,
    request: Request,
    window: str = Query(default="7d"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    hours, canonical = _resolve_window_hours(window)

    cache_key = ("edge-history", slug, canonical)
    if settings.desk_cache_enabled:
        cached_body = opportunities_cache.get(cache_key, settings.desk_cache_ttl_sec)
        if cached_body is not None:
            return etag_json_response(request, {**cached_body, "cached": True})

    market_model = await MarketService(db).get_market_by_slug(slug)
    found = market_model is not None

    since = datetime.now(UTC) - timedelta(hours=hours)
    series = await _build_series(db, slug, since) if found else []

    response: dict[str, Any] = {
        "found": found,
        "slug": slug,
        "window": canonical,
        "window_hours": hours,
        "series": series,
        "count": len(series),
        "max_points": _MAX_POINTS,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": EDGE_HISTORY_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
        "cached": False,
    }
    if settings.desk_cache_enabled:
        opportunities_cache.put(cache_key, response)
    return etag_json_response(request, response)
