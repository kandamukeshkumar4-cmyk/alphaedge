"""G03 — news:mispricing signal (fixture-driven, no network)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import SignalEvent
from app.signals.news_mispricing import (
    NEWS_MISPRICING_SIGNAL_TYPE,
    NewsMispricingInput,
    evaluate_news_mispricing,
    news_mispricing_to_events,
)
from app.workers.tasks import run_news_mispricing_scan

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "news" / "mispricing_cases.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def test_evaluate_news_mispricing_boundaries():
    now = _ts("2026-07-09T18:00:00Z")
    fresh = _ts("2026-07-09T17:50:00Z")
    stale = _ts("2026-07-09T12:00:00Z")

    hit = evaluate_news_mispricing(
        model_p=0.62, market_p=0.50, news_ts=fresh, now=now, threshold=0.05
    )
    assert hit.emit is True
    assert hit.gap == pytest.approx(0.12)

    small = evaluate_news_mispricing(
        model_p=0.52, market_p=0.50, news_ts=fresh, now=now, threshold=0.05
    )
    assert small.emit is False
    assert small.reason == "gap_below_threshold"

    old = evaluate_news_mispricing(
        model_p=0.70, market_p=0.40, news_ts=stale, now=now, window_sec=900
    )
    assert old.emit is False
    assert old.reason == "news_stale"


def test_fixture_cases_to_events():
    payload = _load()
    now = _ts(payload["now"])
    items = [
        NewsMispricingInput(
            market_slug=c["market_slug"],
            platform=c["platform"],
            model_p=c["model_p"],
            market_p=c["market_p"],
            news_id=c["news_id"],
            news_url=c["news_url"],
            news_ts=_ts(c["news_ts"]),
            headline=c["headline"],
        )
        for c in payload["cases"]
    ]
    events = news_mispricing_to_events(
        items,
        now=now,
        threshold=payload["threshold"],
        window_sec=payload["window_sec"],
    )
    assert len(events) == 1
    ev = events[0]
    assert ev["signal_type"] == NEWS_MISPRICING_SIGNAL_TYPE
    assert ev["market_id"] == "pm-will-lakers-beat-celtics"
    assert ev["payload"]["news_id"] == "news-lal-injury-1"
    assert ev["payload"]["news_url"] == "https://example.test/news/lal-injury"
    assert ev["payload"]["model_p"] == pytest.approx(0.62)
    assert ev["payload"]["market_p"] == pytest.approx(0.50)
    assert ev["payload"]["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_run_news_mispricing_scan_persists(db_session, monkeypatch):
    from datetime import timedelta

    from app.db.models import Market, MarketStatus, OddsSnapshot
    from app.services.forecast_service import MarketDetailForecastResult
    from app.signals.news_signal import NewsSignal

    now = datetime.now(UTC)
    market = Market(
        slug="pm-will-lakers-beat-celtics",
        title="Will the Lakers beat the Celtics?",
        question="Will the Lakers beat the Celtics?",
        category="NBA",
        status=MarketStatus.OPEN,
        source="polymarket",
        volume=100000,
    )
    db_session.add(market)
    db_session.add(
        OddsSnapshot(
            market_slug="pm-will-lakers-beat-celtics",
            implied_yes=Decimal("0.50"),
            source="fixture",
            captured_at=now - timedelta(minutes=2),
        )
    )
    await db_session.flush()

    async def fake_fetch(topic: str, *, timeout: float = 30.0):
        return NewsSignal(
            topic=topic,
            sentiment_score=0.4,
            volume_score=0.8,
            polymarket_consensus=0.5,
            headline="Lakers star ruled out",
            sources_count=3,
            news_id="news-lal-injury-1",
            news_url="https://example.test/news/lal-injury",
            published_at=now - timedelta(minutes=5),
        )

    monkeypatch.setattr(
        "app.signals.news_signal.fetch_news_signal",
        fake_fetch,
    )

    def fake_predict(slug: str, implied_yes: float = 0.5) -> MarketDetailForecastResult:
        return MarketDetailForecastResult(
            model_prob=0.62, clv_gate_passed=True, provisional=False
        )

    monkeypatch.setattr(
        "app.services.forecast_service.ForecastService.predict",
        staticmethod(fake_predict),
    )

    result = await run_news_mispricing_scan(db_session)
    assert result["emitted"] >= 1

    rows = list(
        (
            await db_session.scalars(
                select(SignalEvent).where(
                    SignalEvent.signal_type == NEWS_MISPRICING_SIGNAL_TYPE
                )
            )
        ).all()
    )
    assert len(rows) >= 1
    assert rows[0].payload["news_id"] == "news-lal-injury-1"
    assert rows[0].payload["news_url"] == "https://example.test/news/lal-injury"
