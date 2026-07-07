from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.forecasting.ensemble_providers import ensemble_forecast
from app.forecasting.predictor import predict_market
from app.forecasting.router import ModelRouter
from app.schemas.market_prediction import (
    EnsembleForecast,
    MarketPredictionResponse,
)
from app.services import market_service
from app.services.market_service import CATALOG_SLUGS

router = APIRouter(prefix="/api/v1", tags=["markets"])
settings = get_settings()


def _implied_prob_from_catalog(slug: str) -> float:
    catalog = getattr(market_service, "CATALOG", None)
    if isinstance(catalog, dict) and slug in catalog:
        entry = catalog[slug]
        if isinstance(entry, dict):
            if "implied_prob" in entry:
                return float(entry["implied_prob"])
            if "implied_yes" in entry:
                return float(entry["implied_yes"])
    return 0.5


def _is_provisional(slug: str, is_edge: bool, reason: str) -> bool:
    if slug.startswith("wc2026-"):
        return True
    if not is_edge and "no resolved" in reason:
        return True
    return False


@router.get("/markets/{slug}/prediction", response_model=MarketPredictionResponse)
async def get_market_prediction(slug: str) -> MarketPredictionResponse:
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=404, detail="Market not found")

    implied_prob = _implied_prob_from_catalog(slug)
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
        predicted_prob=prediction.predicted_prob,
        confidence=prediction.confidence,
        edge=prediction.edge,
        is_edge=prediction.is_edge,
        reason=prediction.reason,
        provisional=_is_provisional(slug, prediction.is_edge, prediction.reason),
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
