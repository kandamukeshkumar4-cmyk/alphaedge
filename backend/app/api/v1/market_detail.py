from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import MarketResolution
from app.db.session import get_db
from app.schemas.market import (
    MarketDetailForecast,
    MarketDetailOutcome,
    MarketDetailResponse,
)
from app.services.forecast_service import ForecastService
from app.services.market_service import CATALOG_SLUGS, MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["markets"])
settings = get_settings()


@router.get("/markets/{slug}/detail", response_model=MarketDetailResponse)
async def get_market_detail(slug: str, db: AsyncSession = Depends(get_db)):
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=404, detail="Market not found")

    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    book = await OrderBookService(db).get_l2(market.id, depth=1)
    yes_price = _best_outcome_price(book.get("yes", {}), 0.5)
    no_price = _best_outcome_price(book.get("no", {}), round(1.0 - yes_price, 4))

    resolution = await db.scalar(select(MarketResolution).where(MarketResolution.slug == slug))
    resolved = resolution is not None or market.status.value == "resolved"
    resolution_outcome = resolution.outcome if resolution is not None else None
    winning_outcome = resolution_outcome
    if winning_outcome is None and market.winning_outcome is not None:
        winning_outcome = market.winning_outcome.value.upper()
    resolved_at = market.resolved_at

    forecast_payload: MarketDetailForecast | None = None
    forecast_result = ForecastService.predict(slug, implied_yes=yes_price)
    if forecast_result is not None:
        forecast_payload = MarketDetailForecast(
            model_prob=forecast_result.model_prob,
            clv_gate_passed=forecast_result.clv_gate_passed,
            provisional=forecast_result.provisional,
        )

    return MarketDetailResponse(
        slug=market.slug,
        title=market.title,
        category=market.category,
        status=market.status.value,
        outcomes=[
            MarketDetailOutcome(label="YES", implied_prob=yes_price, price=yes_price),
            MarketDetailOutcome(label="NO", implied_prob=no_price, price=no_price),
        ],
        forecast=forecast_payload,
        volume_usd=market.volume,
        traders=market.traders,
        resolution_criteria=market.resolution,
        paper_trading_only=settings.paper_trading_only,
        resolved=resolved,
        resolution_outcome=resolution_outcome,
        winning_outcome=winning_outcome,
        resolved_at=resolved_at,
    )


def _best_outcome_price(book_side: dict, fallback: float) -> float:
    asks = book_side.get("asks") or []
    bids = book_side.get("bids") or []
    if asks:
        return round(float(asks[0]["price"]), 4)
    if bids:
        return round(float(bids[0]["price"]), 4)
    return round(fallback, 4)
