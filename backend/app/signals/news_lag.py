"""News -> price lag detector (Hermes layer 3).

When a high-relevance headline lands but the market has NOT yet repriced, emit a
``news_arrival(unpriced=True)`` DeltaEvent — the analyst's best moment. Sentiment is
metadata / a directional vote only (guardrail 3): the delta is one alignment layer,
never a standalone trigger.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewsLagThresholds:
    lag_window_sec: float = 300.0
    min_relevance: float = 0.5
    move_threshold: float = 0.02  # probability move below which the market is "unpriced"


@dataclass(frozen=True)
class NewsLagResult:
    unpriced: bool
    direction: Optional[str]  # "up" / "down" / None (neutral)
    relevance: float
    price_move: float
    reason: str


def _direction_from_sentiment(sentiment: float) -> Optional[str]:
    if sentiment > 0:
        return "up"
    if sentiment < 0:
        return "down"
    return None


def evaluate_news_lag(
    *,
    relevance: float,
    sentiment: float,
    news_ts: datetime,
    now: datetime,
    price_at_news: Optional[float],
    price_now: Optional[float],
    thresholds: NewsLagThresholds,
) -> NewsLagResult:
    """Pure decision: has a relevant headline gone unpriced within the window?"""
    direction = _direction_from_sentiment(sentiment)
    move = (
        abs(price_now - price_at_news)
        if price_at_news is not None and price_now is not None
        else 0.0
    )

    age = (now - news_ts).total_seconds()
    if age > thresholds.lag_window_sec:
        return NewsLagResult(False, direction, relevance, move, "stale")
    if relevance < thresholds.min_relevance:
        return NewsLagResult(False, direction, relevance, move, "low_relevance")
    if direction is None:
        return NewsLagResult(False, None, relevance, move, "neutral_sentiment")
    if price_at_news is not None and price_now is not None and move >= thresholds.move_threshold:
        return NewsLagResult(False, direction, relevance, move, "priced_in")
    return NewsLagResult(True, direction, relevance, move, "unpriced")


def news_lag_to_delta_event(
    result: NewsLagResult,
    market_slug: str,
    *,
    sentiment: float,
    source: str = "news",
):
    """Convert an unpriced result into a NEWS_ARRIVAL DeltaEvent, else None."""
    if not result.unpriced or result.direction is None:
        return None
    from app.signals.diff_engine import DeltaEvent, DeltaKind

    return DeltaEvent(
        market_slug=market_slug,
        source=source,
        kind=DeltaKind.NEWS_ARRIVAL,
        direction=result.direction,
        magnitude=round(result.relevance, 4),
        detail={
            "unpriced": True,
            "relevance": round(result.relevance, 4),
            "sentiment": round(sentiment, 4),
            "price_move": round(result.price_move, 6),
        },
        occurred_ts=datetime.now(UTC),
    )


class NewsLagService:
    """Reads price history from odds_snapshots and emits news_arrival deltas."""

    def __init__(self, session, thresholds: NewsLagThresholds | None = None):
        self.session = session
        self.thresholds = thresholds or NewsLagThresholds()

    async def _price_at(self, market_slug: str, at_ts: datetime | None) -> float | None:
        from sqlalchemy import select

        from app.db.models import OddsSnapshot

        query = (
            select(OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == market_slug)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        if at_ts is not None:
            query = (
                select(OddsSnapshot.implied_yes)
                .where(
                    OddsSnapshot.market_slug == market_slug,
                    OddsSnapshot.captured_at <= at_ts,
                )
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(1)
            )
        row = await self.session.scalar(query)
        return float(row) if row is not None else None

    async def detect(
        self,
        market_slug: str,
        *,
        relevance: float,
        sentiment: float,
        news_ts: datetime,
        now: datetime | None = None,
    ) -> NewsLagResult:
        """Evaluate lag for a market and, if unpriced+directional, persist the delta
        and feed the T04 alignment scorer."""
        now = now or datetime.now(UTC)
        price_at_news = await self._price_at(market_slug, news_ts)
        price_now = await self._price_at(market_slug, None)
        result = evaluate_news_lag(
            relevance=relevance,
            sentiment=sentiment,
            news_ts=news_ts,
            now=now,
            price_at_news=price_at_news,
            price_now=price_now,
            thresholds=self.thresholds,
        )
        event = news_lag_to_delta_event(result, market_slug, sentiment=sentiment)
        if event is None:
            return result

        from app.core.config import get_settings
        from app.signals.diff_engine import persist_deltas

        await persist_deltas(self.session, [event])
        if get_settings().alignment_enabled:
            from app.signals.alignment import get_alignment_scorer, persist_alignment

            score = get_alignment_scorer().observe_deltas([event])
            if score is not None:
                await persist_alignment(self.session, score)
        return result
