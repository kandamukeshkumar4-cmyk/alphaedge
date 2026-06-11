from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.forecasting.predictor import predict_market
from app.schemas.market_prediction import MarketPredictionResponse
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

    return MarketPredictionResponse(
        slug=slug,
        predicted_prob=prediction.predicted_prob,
        confidence=prediction.confidence,
        edge=prediction.edge,
        is_edge=prediction.is_edge,
        reason=prediction.reason,
        provisional=_is_provisional(slug, prediction.is_edge, prediction.reason),
        paper_trading_only=settings.paper_trading_only,
    )
