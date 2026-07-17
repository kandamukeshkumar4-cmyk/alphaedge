"""Loop V61 S2 sentiment-trend persistence and no-lookahead tests."""

from datetime import UTC, datetime, timedelta

import pytest

from app.signals.sentiment_trend import SentimentObservation, load_sentiment_trend, trend_features


def test_trend_features_are_bounded_and_reject_post_close_observations():
    close_at = datetime(2026, 7, 17, 12, tzinfo=UTC)
    features = trend_features(
        [
            SentimentObservation(-0.8, close_at - timedelta(minutes=3)),
            SentimentObservation(-0.2, close_at - timedelta(minutes=2)),
            SentimentObservation(0.9, close_at - timedelta(minutes=1)),
            SentimentObservation(-1.0, close_at + timedelta(minutes=1)),
        ],
        as_of=close_at,
    )
    assert features["available"] is True
    assert features["direction"] == 1.0
    assert features["acceleration"] == 0.4
    assert features["samples"] == 3


@pytest.mark.asyncio
async def test_load_sentiment_trend_uses_capture_time_and_market_close(db_session):
    from app.db.models import MarketSentimentSnapshot

    close_at = datetime(2026, 7, 17, 12, tzinfo=UTC)
    db_session.add_all([
        MarketSentimentSnapshot(market_slug="m1", sentiment_score=-0.2, volume_score=0.5, sources_count=2, captured_at=close_at - timedelta(minutes=2)),
        MarketSentimentSnapshot(market_slug="m1", sentiment_score=0.3, volume_score=0.6, sources_count=3, captured_at=close_at - timedelta(minutes=1)),
        MarketSentimentSnapshot(market_slug="m1", sentiment_score=-0.9, volume_score=0.9, sources_count=9, captured_at=close_at + timedelta(minutes=1)),
    ])
    await db_session.flush()
    features = await load_sentiment_trend(
        db_session,
        market_slug="m1",
        as_of=close_at + timedelta(hours=1),
        close_at=close_at,
    )
    assert features["available"] is True
    assert features["direction"] == 0.5
    assert features["samples"] == 2
