"""M01 — Personalized home aggregate (Loop V8).

``GET /api/v1/home`` — ONE call that composes the landing surface from EXISTING
services so the home page renders without a fan-out of per-widget requests:

* ``signals`` — the top-N most recent alert-family SignalEvents, carrying the
  H03 citation fields (reuses the J02 ``_build_alert_feed`` builder);
* ``digest`` — the L02 per-family alert digest summary over a bounded window
  (reuses ``get_alerts_digest`` verbatim);
* ``model_ab`` — the I02/J03 resolved-count + A/B readiness numbers (reuses
  ``count_resolved_outcomes`` + the A/B gate constants; the deployed default
  model is NEVER flipped here);
* ``top_markets`` — active public markets ranked by recent price movement and
  close proximity (reuses ``MarketService.list_public_markets``).

**PUBLIC GET with OPTIONAL JWT** (``get_optional_user``): anonymous callers get
the four non-personal sections above with ``watchlist_count = null`` and
``watchlist_alerts = []``. When a valid token is present it ALSO enriches with
the caller's K03 watchlist count + recent watchlist alerts.

Read-only composition of existing stores only — no new pipeline, no new table,
persists nothing, and the order write path is never imported. Honest empties
everywhere (empty DB → empty lists / zero counts, never fabricated data).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts_feed import (
    _build_alert_feed,
    _watchlist_slugs,
    get_alerts_digest,
)
from app.api.v1.deps import get_optional_user
from app.core.config import get_settings
from app.core.http_etag import etag_json_response
from app.db.models import User
from app.db.session import get_db
from app.ml.ab_harness import (
    resolved_count_readout,
)
from app.services.market_service import MarketService

router = APIRouter(prefix="/api/v1", tags=["home"])
settings = get_settings()

HOME_DISCLAIMER = (
    "Personalized intelligence home — recent signals, the alert digest, model "
    "A/B readiness and top markets composed from existing analysis surfaces. "
    "Signal only; paper trading only — simulated funds, no execution."
)


async def _top_markets(db: AsyncSession, limit: int) -> list[dict[str, Any]]:
    """Active, non-decided markets. Compact projection only."""
    markets, _ = await MarketService(db).list_public_markets(sort="active")
    top = markets[:limit]
    return [
        {
            "slug": m.slug,
            "title": m.title,
            "category": m.category,
            "volume": m.volume,
            "yes_price": m.yes_price,
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
        }
        for m in top
    ]


async def _model_ab_status(db: AsyncSession) -> dict[str, Any]:
    """I02/J03 readiness numbers only — cheap, and NEVER runs the heavy A/B
    training on a home render. Reports whether the harness is eligible; the
    deployed default model is never flipped here."""
    readout = await resolved_count_readout(db)
    return {
        "resolved_count": readout["resolved_count"],
        "forecast_scored_count": readout["forecast_scored_count"],
        "correlation_clusters": readout["correlation_clusters"],
        "ab_threshold": readout["ab_threshold"],
        "ab_ready": readout["ab_ready"],
        "model_default": readout["default_model"],
        "lightgbm_available": readout["lightgbm_available"],
        "applied": False,
    }


@router.get("/home")
async def get_home(
    request: Request,
    signals_limit: int = Query(default=5, ge=1, le=25),
    markets_limit: int = Query(default=5, ge=1, le=25),
    digest_window: str = Query(default="24h"),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # Recent alert-family signals with H03 citations (J02 builder, no filter).
    signals_feed = await _build_alert_feed(
        db, effective_slugs=None, scope="all", since=None, limit=signals_limit
    )
    # L02 digest summary over the requested window (reused verbatim).
    digest = await get_alerts_digest(window=digest_window, slugs=None, top=5, db=db)
    model_ab = await _model_ab_status(db)
    top_markets = await _top_markets(db, markets_limit)

    # Personal enrichment only for an authenticated caller (K03 watchlist).
    watchlist_count: int | None = None
    watchlist_alerts: list[dict[str, Any]] = []
    if current_user is not None:
        slugs = await _watchlist_slugs(db, current_user.id)
        watchlist_count = len(slugs)
        wl_feed = await _build_alert_feed(
            db,
            effective_slugs=slugs,
            scope="watchlist",
            since=None,
            limit=signals_limit,
        )
        watchlist_alerts = wl_feed.model_dump(mode="json")["items"]

    body: dict[str, Any] = {
        "authenticated": current_user is not None,
        "signals": signals_feed.model_dump(mode="json")["items"],
        "digest": digest.model_dump(mode="json"),
        "model_ab": model_ab,
        "top_markets": top_markets,
        "watchlist_count": watchlist_count,
        "watchlist_alerts": watchlist_alerts,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": HOME_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    # M03: additive weak-ETag + If-None-Match → 304. The 200 body is unchanged.
    return etag_json_response(request, body)
