"""Confluence scoreboard lenses for the research terminal (Loop V79 A3).

Six deterministic lenses, each emitting {lens, read, why}. Reads are derived
from the same read-only services as the step executor — never invented.
Shape idea mirrors ai-hedge-fund per-analyst signal dicts (signal + reason),
not their trading code.
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, OddsSnapshot
from app.services.forecast_service import ForecastService
from app.services.market_service import MarketService
from app.services.venue_gap_service import VenueGapService
from app.services.whale_flow_service import WhaleFlowService
from app.signals.news_signal import fetch_news_signal
from app.signals.sentiment_trend import load_sentiment_trend

Read = Literal["bullish", "bearish", "neutral", "cautious"]
_ALLOWED_READS = frozenset({"bullish", "bearish", "neutral", "cautious"})
_LENS_KEYS = (
    "price_action",
    "whale_flow",
    "news",
    "sentiment",
    "model_vs_market",
    "time_to_lock",
)


async def _price_move_24h(db: AsyncSession, slug: str) -> tuple[float | None, float | None, float | None]:
    """Return (move_pct, first, last) over ~24h odds snapshots."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=24)
    rows = (
        await db.execute(
            select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at >= cutoff,
            )
            .order_by(OddsSnapshot.captured_at.asc())
        )
    ).all()
    if len(rows) < 2:
        return None, None, None
    first = float(rows[0][0])
    last = float(rows[-1][0])
    if first == 0:
        return None, first, last
    move_pct = ((last - first) / first) * 100.0
    return move_pct, first, last


def _majority_verdict(reads: list[str]) -> str:
    counts = Counter(r for r in reads if r in _ALLOWED_READS)
    if not counts:
        return "neutral"
    top = counts.most_common()
    if len(top) >= 2 and top[0][1] == top[1][1]:
        return "neutral"
    return top[0][0]


async def build_scoreboard(db: AsyncSession, market: Market) -> dict[str, Any]:
    """Build exactly six confluence lenses and a majority verdict."""
    slug = market.slug
    lenses: list[dict[str, str]] = []

    # 1) price_action
    move_pct, first, last = await _price_move_24h(db, slug)
    if move_pct is None:
        lenses.append(
            {
                "lens": "price_action",
                "read": "neutral",
                "why": "Insufficient 24h price history to measure a move.",
            }
        )
    elif move_pct > 2.0:
        lenses.append(
            {
                "lens": "price_action",
                "read": "bullish",
                "why": f"24h move {move_pct:+.2f}% (from {first:.4f} to {last:.4f}).",
            }
        )
    elif move_pct < -2.0:
        lenses.append(
            {
                "lens": "price_action",
                "read": "bearish",
                "why": f"24h move {move_pct:+.2f}% (from {first:.4f} to {last:.4f}).",
            }
        )
    else:
        lenses.append(
            {
                "lens": "price_action",
                "read": "neutral",
                "why": f"24h move {move_pct:+.2f}% (from {first:.4f} to {last:.4f}) within ±2%.",
            }
        )

    # 2) whale_flow
    pressure = await WhaleFlowService(db).pressure_for(slug)
    gap = await VenueGapService(db).gap_for_slug(slug)
    if pressure.event_count <= 0 and gap is None:
        lenses.append(
            {
                "lens": "whale_flow",
                "read": "neutral",
                "why": "No whale events or venue gap signals for this market.",
            }
        )
    elif pressure.pressure > 0.15:
        lenses.append(
            {
                "lens": "whale_flow",
                "read": "bullish",
                "why": (
                    f"Whale pressure {pressure.pressure:+.4f} across "
                    f"{pressure.event_count} events (net notional {pressure.net_notional})."
                ),
            }
        )
    elif pressure.pressure < -0.15:
        lenses.append(
            {
                "lens": "whale_flow",
                "read": "bearish",
                "why": (
                    f"Whale pressure {pressure.pressure:+.4f} across "
                    f"{pressure.event_count} events (net notional {pressure.net_notional})."
                ),
            }
        )
    else:
        gap_note = f", venue abs_gap={float(gap.abs_gap):.4f}" if gap is not None else ""
        lenses.append(
            {
                "lens": "whale_flow",
                "read": "neutral",
                "why": (
                    f"Whale pressure {pressure.pressure:+.4f} across "
                    f"{pressure.event_count} events{gap_note}."
                ),
            }
        )

    # 3) news
    news = await fetch_news_signal(slug)
    if news is None:
        lenses.append(
            {
                "lens": "news",
                "read": "neutral",
                "why": "No news signal available for this market.",
            }
        )
    elif news.sentiment_score > 0.15:
        lenses.append(
            {
                "lens": "news",
                "read": "bullish",
                "why": (
                    f"News sentiment {news.sentiment_score:+.4f} "
                    f"(sources={news.sources_count})."
                ),
            }
        )
    elif news.sentiment_score < -0.15:
        lenses.append(
            {
                "lens": "news",
                "read": "bearish",
                "why": (
                    f"News sentiment {news.sentiment_score:+.4f} "
                    f"(sources={news.sources_count})."
                ),
            }
        )
    else:
        lenses.append(
            {
                "lens": "news",
                "read": "neutral",
                "why": (
                    f"News sentiment {news.sentiment_score:+.4f} "
                    f"(sources={news.sources_count}) near flat."
                ),
            }
        )

    # 4) sentiment
    trend = await load_sentiment_trend(db, market_slug=slug, as_of=datetime.now(UTC))
    direction = trend.get("direction")
    if not trend.get("available") or direction is None:
        lenses.append(
            {
                "lens": "sentiment",
                "read": "neutral",
                "why": "No sentiment trend samples available for this market.",
            }
        )
    else:
        d = float(direction)
        if d > 0.05:
            read: Read = "bullish"
        elif d < -0.05:
            read = "bearish"
        else:
            read = "neutral"
        lenses.append(
            {
                "lens": "sentiment",
                "read": read,
                "why": f"Sentiment direction {d:+.4f} (samples={trend.get('samples')}).",
            }
        )

    # 5) model_vs_market
    public = await MarketService(db).get_public_market_by_slug(slug)
    market_p = float(public.yes_price) if public and public.yes_price is not None else None
    implied = market_p if market_p is not None else 0.5
    forecast = ForecastService.predict(slug, implied_yes=implied)
    if forecast is None or market_p is None:
        lenses.append(
            {
                "lens": "model_vs_market",
                "read": "neutral",
                "why": "Model or market probability unavailable for comparison.",
            }
        )
    else:
        model_p = float(forecast.model_prob)
        diff_pp = (model_p - market_p) * 100.0
        if diff_pp > 2.0:
            mv_read: Read = "bullish"
        elif diff_pp < -2.0:
            mv_read = "bearish"
        else:
            mv_read = "neutral"
        lenses.append(
            {
                "lens": "model_vs_market",
                "read": mv_read,
                "why": (
                    f"Model {model_p:.4f} minus market {market_p:.4f} "
                    f"= {diff_pp:+.2f}pp."
                ),
            }
        )

    # 6) time_to_lock
    now = datetime.now(UTC)
    lock_at = market.lock_at
    if lock_at is None:
        lenses.append(
            {
                "lens": "time_to_lock",
                "read": "neutral",
                "why": "No lock_at timestamp on this market.",
            }
        )
    else:
        if lock_at.tzinfo is None:
            lock_at = lock_at.replace(tzinfo=UTC)
        hours = (lock_at - now).total_seconds() / 3600.0
        if hours < 24.0:
            lenses.append(
                {
                    "lens": "time_to_lock",
                    "read": "cautious",
                    "why": f"Lock in {hours:.1f}h (< 24h).",
                }
            )
        else:
            lenses.append(
                {
                    "lens": "time_to_lock",
                    "read": "neutral",
                    "why": f"Lock in {hours:.1f}h (>= 24h).",
                }
            )

    assert len(lenses) == 6
    assert {lens["lens"] for lens in lenses} == set(_LENS_KEYS)
    for lens in lenses:
        assert lens["read"] in _ALLOWED_READS

    verdict = _majority_verdict([lens["read"] for lens in lenses])
    return {"verdict": verdict, "lenses": lenses}
