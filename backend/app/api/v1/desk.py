"""Single-market desk aggregate (H01, Loop V3).

``GET /api/v1/desk?slug=...`` — composes, in ONE response, everything the
market page's intelligence panel needs so it renders with a single call
(instead of flooding the API with per-widget requests):

* market snapshot (public market + top-of-book) — reuses ``MarketService`` /
  ``OrderBookService``;
* latest model-vs-market edge — reuses the newest ``PredictionLog`` for the
  slug, same edge math as the market snapshot route;
* smart-money summary — reuses the G07 ``build_smart_money_summary`` verbatim;
* cross-venue arb match if any — reuses the G02 ``VenueMatchService`` persisted
  matches;
* latest ``SignalEvent`` rows for the slug.

Composition of EXISTING services only — no new pipelines, no new tables.
READ-ONLY analysis surface: ``signal_only`` is always true, the order write
path (risk validation / order intents / order submission) is never imported,
and an unknown slug returns 200 with honest empties (never a 404 and never
fabricated data).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.smart_money import build_smart_money_summary
from app.core.config import get_settings
from app.db.models import PredictionLog
from app.db.session import get_db
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService
from app.services.venue_match_service import VenueMatchService

router = APIRouter(prefix="/api/v1", tags=["desk"])
settings = get_settings()

DESK_DISCLAIMER = (
    "Research desk aggregate — market snapshot, model edge, smart-money and "
    "cross-venue observations composed from existing analysis surfaces. "
    "Signal only; paper trading only — simulated funds, no execution."
)


def _edge_vs_book(predicted_prob: float, book: dict[str, Any]) -> float | None:
    """Model probability minus the best reference YES price (asks, else bids).

    Same math as ``GET /api/v1/markets/{slug}/snapshot`` — kept local so this
    read-only surface never imports the order-path module.
    """
    yes_book = book.get("yes", {}) if book else {}
    reference_levels = yes_book.get("asks") or yes_book.get("bids") or []
    if not reference_levels:
        return None
    return round(predicted_prob - float(reference_levels[0]["price"]), 4)


async def _latest_edge(
    db: AsyncSession, slug: str, book: dict[str, Any] | None
) -> dict[str, Any] | None:
    result = await db.execute(
        select(PredictionLog)
        .where(PredictionLog.market_slug == slug)
        .order_by(PredictionLog.predicted_at.desc())
        .limit(1)
    )
    prediction = result.scalar_one_or_none()
    if prediction is None:
        return None
    predicted_prob = float(prediction.predicted_prob)
    return {
        "predicted_prob": predicted_prob,
        "confidence": float(prediction.confidence),
        "edge_vs_book": _edge_vs_book(predicted_prob, book or {}),
        "input_feature_hash": prediction.input_feature_hash,
        "predicted_at": prediction.predicted_at,
        "source": "prediction_log",
    }


async def _arb_match(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    """Highest-confidence persisted PM↔Kalshi match touching this slug (G02)."""
    matches = await VenueMatchService(db).list_matches()
    for match in matches:  # already ordered by confidence desc
        if match.pm_slug == slug or match.ks_slug == slug:
            return {
                "pm_slug": match.pm_slug,
                "ks_slug": match.ks_slug,
                "pm_title": match.pm_title,
                "ks_title": match.ks_title,
                "confidence": float(match.confidence),
                "reasons": list(match.reasons or []),
                "stale": bool(match.stale),
                "matched_at": match.matched_at,
                "updated_at": match.updated_at,
            }
    return None


async def _latest_signals(
    db: AsyncSession, slug: str, limit: int
) -> list[dict[str, Any]]:
    from app.db.models import SignalEvent

    stmt = (
        select(SignalEvent)
        .where(SignalEvent.market_id == slug)
        .order_by(SignalEvent.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(event.id),
            "signal_type": event.signal_type,
            "platform": event.platform,
            "market_id": event.market_id,
            "headline_eligible": event.headline_eligible,
            "payload": dict(event.payload or {}),
            "created_at": event.created_at,
        }
        for event in rows
    ]


@router.get("/desk")
async def get_desk(
    slug: str = Query(..., min_length=1, max_length=128),
    hours: int = Query(default=24, ge=1, le=168),
    top_n: int = Query(default=5, ge=1, le=25),
    signals_limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = MarketService(db)
    market_model = await svc.get_market_by_slug(slug)
    market = await svc.get_public_market_by_slug(slug)
    market_found = market_model is not None and market is not None

    book: dict[str, Any] | None = None
    edge: dict[str, Any] | None = None
    if market_found:
        book = await OrderBookService(db).get_l2(market_model.id, depth=10)
        edge = await _latest_edge(db, slug, book)

    smart_money = await build_smart_money_summary(
        db, slug, hours=hours, top_n=top_n
    )
    arb = await _arb_match(db, slug)
    signals = await _latest_signals(db, slug, signals_limit)

    return {
        "slug": slug,
        "market_found": market_found,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": DESK_DISCLAIMER,
        "market": market.model_dump(mode="json") if market else None,
        "book": book,
        "edge": edge,
        "smart_money": smart_money,
        "arb": arb,
        "signals": signals,
        "generated_at": datetime.now(UTC).isoformat(),
    }
