"""T06 — news->price lag detector: boundaries + end-to-end delta emission."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.models import OddsSnapshot, SignalEvent
from app.signals.diff_engine import DeltaKind
from app.signals.news_lag import (
    NewsLagThresholds,
    evaluate_news_lag,
    news_lag_to_delta_event,
)

T0 = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
THR = NewsLagThresholds(lag_window_sec=300.0, min_relevance=0.5, move_threshold=0.02)


def _eval(**kw):
    base = dict(
        relevance=0.8,
        sentiment=0.6,
        news_ts=T0,
        now=T0 + timedelta(seconds=60),
        price_at_news=0.50,
        price_now=0.505,  # moved 0.5c < 2c threshold -> unpriced
        thresholds=THR,
    )
    base.update(kw)
    return evaluate_news_lag(**base)


def test_unpriced_high_relevance_recent_fires_up():
    r = _eval()
    assert r.unpriced is True
    assert r.direction == "up"
    assert r.reason == "unpriced"


def test_negative_sentiment_direction_down():
    assert _eval(sentiment=-0.7).direction == "down"


def test_priced_in_does_not_fire():
    r = _eval(price_now=0.55)  # moved 5c >= 2c -> already repriced
    assert r.unpriced is False
    assert r.reason == "priced_in"


def test_stale_headline_does_not_fire():
    r = _eval(now=T0 + timedelta(seconds=301))  # past 300s window
    assert r.unpriced is False
    assert r.reason == "stale"


def test_low_relevance_does_not_fire():
    r = _eval(relevance=0.49)
    assert r.unpriced is False
    assert r.reason == "low_relevance"


def test_neutral_sentiment_no_vote():
    r = _eval(sentiment=0.0)
    assert r.unpriced is False
    assert r.reason == "neutral_sentiment"
    assert r.direction is None


def test_move_threshold_boundary_exactly_at_is_priced_in():
    # exactly at threshold counts as priced-in (>=)
    r = _eval(price_now=0.52)  # move 0.02 == threshold
    assert r.reason == "priced_in"


def test_missing_price_history_treated_as_unpriced():
    r = _eval(price_at_news=None, price_now=None)
    assert r.unpriced is True  # no reprice observable -> the whole point


def test_delta_event_only_when_unpriced_directional():
    unpriced = _eval()
    assert news_lag_to_delta_event(unpriced, "m", sentiment=0.6).kind is DeltaKind.NEWS_ARRIVAL
    priced = _eval(price_now=0.60)
    assert news_lag_to_delta_event(priced, "m", sentiment=0.6) is None
    neutral = _eval(sentiment=0.0)
    assert news_lag_to_delta_event(neutral, "m", sentiment=0.0) is None


# --- end-to-end -----------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_persists_news_arrival(db_session):
    from app.signals.news_lag import NewsLagService

    slug = "pm-news-test"
    # price snapshot before the news, and a barely-moved one after
    db_session.add(
        OddsSnapshot(
            id=uuid4(), market_slug=slug, implied_yes=Decimal("0.50"),
            source="polymarket-live", captured_at=T0 - timedelta(seconds=30),
            book="polymarket", market_type="binary", outcome_name="Yes",
            price=Decimal("0.50"),
        )
    )
    db_session.add(
        OddsSnapshot(
            id=uuid4(), market_slug=slug, implied_yes=Decimal("0.505"),
            source="polymarket-live", captured_at=T0 + timedelta(seconds=30),
            book="polymarket", market_type="binary", outcome_name="Yes",
            price=Decimal("0.505"),
        )
    )
    await db_session.flush()

    service = NewsLagService(db_session, thresholds=THR)
    result = await service.detect(
        slug, relevance=0.9, sentiment=0.7, news_ts=T0, now=T0 + timedelta(seconds=60)
    )
    assert result.unpriced is True

    await db_session.flush()
    count = await db_session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.signal_type == "delta:news_arrival"
        )
    )
    assert count == 1


def test_news_lag_event_carries_headline():
    """B04 quality: the news_arrival event stores the real Exa headline so
    downstream briefs cite the story, not a generic 'news up rel=1.0'."""
    from app.signals.news_lag import NewsLagResult, news_lag_to_delta_event

    result = NewsLagResult(
        unpriced=True, direction="up", relevance=0.8, price_move=0.0, reason="unpriced"
    )
    event = news_lag_to_delta_event(
        result, "pm-test", sentiment=0.9, headline="Argentina thrash Cape Verde 4-0"
    )
    assert event is not None
    assert event.detail["headline"] == "Argentina thrash Cape Verde 4-0"

    # No headline supplied -> key absent, never a crash.
    bare = news_lag_to_delta_event(result, "pm-test", sentiment=0.9)
    assert "headline" not in bare.detail
