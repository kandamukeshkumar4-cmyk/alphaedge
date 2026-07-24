"""Public, read-only technical analysis for market outcome-price candles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market_candles import _build_market_candles
from app.core.config import get_settings
from app.db.session import get_db
from app.services.technical_analysis_service import calculate_indicators, classify_regime

router = APIRouter(prefix="/api/v1", tags=["markets"])


@router.get("/markets/{slug}/indicators")
async def get_market_indicators(
    slug: str,
    window: int = Query(default=90),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return technical analysis over the existing public candle series."""
    if window < 20 or window > 365:
        raise HTTPException(status_code=400, detail="window must be between 20 and 365")

    settings = get_settings()
    if not settings.paper_trading_only:
        raise HTTPException(status_code=503, detail="Technical analysis requires paper-trading-only mode")

    candle_payload = await _build_market_candles(slug, window, db)
    candles = candle_payload["candles"]
    closes = [float(candle["close"]) for candle in candles]
    highs = [float(candle["high"]) for candle in candles]
    lows = [float(candle["low"]) for candle in candles]
    indicators = calculate_indicators(closes, highs, lows)

    return {
        "slug": slug,
        "points": [{"t": candle["time"], "close": candle["close"]} for candle in candles],
        "indicators": indicators,
        "regime": classify_regime(indicators),
        "paper_trading_only": True,
    }
