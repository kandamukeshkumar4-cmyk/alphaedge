from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import PredictionLog
from app.db.session import get_db
from app.forecasting.ensemble_providers import ensemble_forecast
from app.forecasting.predictor import predict_market
from app.forecasting.router import ModelRouter
from app.schemas.market_prediction import (
    EnsembleForecast,
    MarketPredictionResponse,
)
from app.services.market_lookup import ImpliedYes, get_catalog_market, resolve_implied_yes
from app.services.market_service import CATALOG_SLUGS

router = APIRouter(prefix="/api/v1", tags=["markets"])
settings = get_settings()

NO_PREDICTION_REASON = "no prediction available: market has no stored price and no logged forecast"


def _is_provisional(slug: str, is_edge: bool, reason: str) -> bool:
    if slug.startswith("wc2026-"):
        return True
    if not is_edge and "no resolved" in reason:
        return True
    return False


async def require_catalog_market(db: AsyncSession, slug: str) -> None:
    """404 only when the catalog itself does not list *slug* (Loop117 D1).

    Seed slugs short-circuit: they are catalog members by construction, and the
    bundled demo catalog must stay readable without a seeded database.
    """
    if slug in CATALOG_SLUGS:
        return
    if await get_catalog_market(db, slug) is None:
        raise HTTPException(status_code=404, detail="Market not found")


async def has_logged_prediction(db: AsyncSession, slug: str) -> bool:
    """True when a ``PredictionLog`` row exists for *slug*."""
    return (
        await db.scalar(
            select(PredictionLog.id).where(PredictionLog.market_slug == slug).limit(1)
        )
    ) is not None


async def prediction_anchor(db: AsyncSession, slug: str) -> ImpliedYes:
    """The unified market-implied YES the whole model chain scores against (D5)."""
    return await resolve_implied_yes(db, slug)


@router.get("/markets/{slug}/prediction", response_model=MarketPredictionResponse)
async def get_market_prediction(
    slug: str, db: AsyncSession = Depends(get_db)
) -> MarketPredictionResponse:
    """Model read for any market the catalog lists.

    Loop117: a market outside the 22-slug seed set is no longer a 404 (D1), the
    market anchor is the same price ``/markets`` serves (D5), and a market with
    nothing to score gets an honest ``available: false`` body rather than a 404
    or a fabricated 0.5 (``prediction_absent_is_honest_not_404``).
    """
    await require_catalog_market(db, slug)

    anchor = await prediction_anchor(db, slug)
    if not anchor.available and not await has_logged_prediction(db, slug):
        return MarketPredictionResponse(
            slug=slug,
            available=False,
            predicted_prob=None,
            confidence=0.0,
            edge=None,
            is_edge=False,
            reason=NO_PREDICTION_REASON,
            provisional=True,
            market_implied=None,
            price_source=anchor.source,
            paper_trading_only=settings.paper_trading_only,
            ensemble=None,
        )

    implied_prob = anchor.price if anchor.price is not None else 0.5
    prediction = await asyncio.to_thread(
        predict_market,
        {
            "market_slug": slug,
            "implied_yes": implied_prob,
        },
    )

    # LLM ensemble (flag-gated) — a SEPARATE probability from the XGBoost judge
    # above. Degrades to None (single-model baseline) with 0 providers or if
    # every provider fails; never raises into the response.
    ensemble = await _maybe_ensemble(slug, implied_prob)

    return MarketPredictionResponse(
        slug=slug,
        available=True,
        predicted_prob=prediction.predicted_prob,
        confidence=prediction.confidence,
        edge=prediction.edge,
        is_edge=prediction.is_edge,
        reason=prediction.reason,
        provisional=_is_provisional(slug, prediction.is_edge, prediction.reason),
        market_implied=anchor.price,
        price_source=anchor.source,
        paper_trading_only=settings.paper_trading_only,
        ensemble=ensemble,
    )


async def _maybe_ensemble(slug: str, implied_prob: float) -> EnsembleForecast | None:
    """Run the LLM ensemble for *slug*, returning None on any degradation path."""
    if not getattr(settings, "ensemble_enabled", False):
        return None
    category = ModelRouter().category_from_features({"market_slug": slug})
    question = f"Will the market '{slug}' resolve YES?"
    context = f"Current market-implied YES probability: {implied_prob:.3f}."
    try:
        result = await ensemble_forecast(
            question, context, settings, market_category=category
        )
    except Exception:  # noqa: BLE001 - the ensemble must never break the baseline
        return None
    if not result:
        return None
    return EnsembleForecast(**result)
