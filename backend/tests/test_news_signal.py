"""Exa news connector tests."""

import pytest


@pytest.mark.asyncio
async def test_exa_news_brief_parses_results(monkeypatch):
    """Exa search results -> NewsSignal with tone-derived sentiment."""
    from app.signals import news_fetcher

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [
                {"title": "Argentina wins epic match", "highlights": ["a strong surge"]},
                {"title": "Cape Verde crash out after loss", "highlights": []},
                {"title": "Neutral preview", "highlights": []},
            ]}

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            assert headers["x-api-key"] == "test-key"
            assert json["category"] == "news"
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("S", (), {"exa_api_key": "test-key"})(),
    )
    signal = await news_fetcher.exa_news_brief("world cup argentina")
    assert signal is not None
    assert signal.sources_count == 3
    assert -1.0 <= signal.sentiment_score <= 1.0
    assert signal.headline == "Argentina wins epic match"


@pytest.mark.asyncio
async def test_exa_news_brief_none_without_key(monkeypatch):
    from app.signals import news_fetcher

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("S", (), {"exa_api_key": ""})(),
    )
    assert await news_fetcher.exa_news_brief("anything") is None


@pytest.mark.asyncio
async def test_news_scan_task_emits_news_arrival_events(db_session, monkeypatch):
    """B04: real news signal -> NewsLagService.detect -> news_arrival SignalEvent."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.models import Market, MarketStatus, OddsSnapshot, SignalEvent
    from app.signals.news_signal import NewsSignal
    from app.workers import tasks as worker_tasks

    market = Market(
        slug="pm-news-scan-test",
        title="Will the news scan work?",
        question="Will it?",
        category="Politics",
        icon="X",
        volume=999_999_999,
        traders=1,
        market_count=1,
        description="t",
        resolution="t",
        status=MarketStatus.OPEN,
        source="polymarket",
        external_slug="news-scan-test",
    )
    db_session.add(market)
    # flat price history -> directional news is "unpriced" -> event fires
    now = datetime.now(UTC)
    for minutes in (120, 60, 1):
        db_session.add(OddsSnapshot(
            market_slug=market.slug,
            implied_yes=Decimal("0.40"),
            source="polymarket.gamma",
            captured_at=now - timedelta(minutes=minutes),
            book="polymarket",
            market_type="binary",
            outcome_name="Yes",
            price=Decimal("0.40"),
        ))
    await db_session.flush()
    await db_session.commit()

    async def fake_fetch(topic, **kw):
        return NewsSignal(
            topic=topic, sentiment_score=0.9, volume_score=0.8,
            polymarket_consensus=None, headline="Big development", sources_count=6,
        )

    monkeypatch.setattr("app.signals.news_signal.fetch_news_signal", fake_fetch)
    # the task imports it locally from news_signal, so patch at source module

    summary = await worker_tasks.news_scan_task({})

    # The task runs on the app-level AsyncSessionLocal (its own DB view), so
    # assert the mechanism: markets scanned, at least one directional news
    # classified as unpriced, and news_arrival SignalEvents persisted.
    assert summary["scanned"] >= 1
    assert any(v == "unpriced" for v in summary["results"].values())
    unpriced_slugs = [s for s, v in summary["results"].items() if v == "unpriced"]
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as check:
        n = len((await check.execute(
            select(SignalEvent).where(
                SignalEvent.market_id.in_(unpriced_slugs),
                SignalEvent.signal_type == "delta:news_arrival",
            )
        )).scalars().all())
    assert n >= 1
