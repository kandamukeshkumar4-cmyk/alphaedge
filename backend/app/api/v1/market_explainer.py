from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agents.graph import prefetch_news_for_market
from app.api.v1.market_prediction import _implied_prob_from_catalog, _is_provisional
from app.forecasting.predictor import predict_market
from app.schemas.market_explainer import MarketExplainerResponse, NewsSignalItem
from app.services.market_service import CATALOG_SLUGS
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
async def explain_market(slug: str, background_tasks: BackgroundTasks) -> MarketExplainerResponse:
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=404, detail="Market not found")

    market_implied = _implied_prob_from_catalog(slug)
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
        paper_trading_only=True,
    )
