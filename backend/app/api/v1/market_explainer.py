from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import prefetch_news_for_market
from app.api.v1.market_prediction import (
    NO_PREDICTION_REASON,
    _is_provisional,
    has_logged_prediction,
    prediction_anchor,
    require_catalog_market,
)
from app.db.session import get_db
from app.forecasting.predictor import predict_market
from app.schemas.market_explainer import MarketExplainerResponse, NewsSignalItem
from app.signals.news_signal import get_cached_signal

router = APIRouter(prefix="/api/v1", tags=["markets"])


def _confidence_label(edge: float) -> str:
    magnitude = abs(edge)
    if magnitude < 0.02:
        return "Weak"
    if magnitude < 0.05:
        return "Moderate"
    return "Strong"


def _edge_direction(edge: float) -> str:
    if edge > 0.005:
        return "model_above_market"
    if edge < -0.005:
        return "model_below_market"
    return "aligned"


def _sentiment_label(score: float) -> str:
    if score > 0.15:
        return "bullish"
    if score < -0.15:
        return "bearish"
    return "neutral"


def _trade_rationale(edge: float, edge_direction: str, news_sentiment: float | None) -> str:
    direction = {
        "model_above_market": "Model leans YES vs market",
        "model_below_market": "Model leans NO vs market",
        "aligned": "Model aligned with market",
    }[edge_direction]
    sentiment = _sentiment_label(news_sentiment if news_sentiment is not None else 0.0)
    edge_pct = f"{abs(edge):.1%}"
    return f"{direction} ({edge_pct} edge); news sentiment {sentiment}."


def _news_items(slug: str) -> list[NewsSignalItem]:
    signal = get_cached_signal(slug)
    if signal is None:
        return []
    return [
        NewsSignalItem(
            headline=signal.headline,
            sentiment_score=signal.sentiment_score,
            volume_score=signal.volume_score,
            sources_count=signal.sources_count,
        )
    ]


@router.get("/markets/{slug}/explain", response_model=MarketExplainerResponse)
async def explain_market(
    slug: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> MarketExplainerResponse:
    """Explain the model-vs-market read for any market the catalog lists.

    Loop117: no seed-set gate (D1), the edge is computed against the same price
    ``/markets`` serves (D5), and a market with nothing to score returns an
    honest ``available: false`` body instead of a 404.
    """
    await require_catalog_market(db, slug)

    anchor = await prediction_anchor(db, slug)
    if not anchor.available and not await has_logged_prediction(db, slug):
        return MarketExplainerResponse(
            slug=slug,
            available=False,
            model_prob=None,
            market_implied=None,
            edge=None,
            edge_direction="unavailable",
            confidence_label="Unavailable",
            news_signals=_news_items(slug),
            trade_rationale=NO_PREDICTION_REASON,
            provisional=True,
            explanation=NO_PREDICTION_REASON,
            price_source=anchor.source,
        )

    market_implied = anchor.price if anchor.price is not None else 0.5
    prediction = await asyncio.to_thread(
        predict_market,
        {"market_slug": slug, "implied_yes": market_implied},
    )
    edge = prediction.edge
    edge_dir = _edge_direction(edge)
    news = _news_items(slug)
    top_sentiment = news[0].sentiment_score if news else None

    if not news:
        background_tasks.add_task(prefetch_news_for_market, slug, timeout=5.0)

    trade_rationale = _trade_rationale(edge, edge_dir, top_sentiment)
    provisional = _is_provisional(slug, prediction.is_edge, prediction.reason)

    return MarketExplainerResponse(
        slug=slug,
        available=True,
        model_prob=round(prediction.predicted_prob, 4),
        market_implied=round(market_implied, 4),
        edge=round(edge, 4),
        edge_direction=edge_dir,
        confidence_label=_confidence_label(edge),
        news_signals=news,
        trade_rationale=trade_rationale,
        provisional=provisional,
        explanation=trade_rationale,
        model_used="deterministic",
        price_source=anchor.source,
        paper_trading_only=True,
    )
