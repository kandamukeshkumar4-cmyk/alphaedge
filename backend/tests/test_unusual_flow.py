"""G04 — anomaly:unusual_flow signal (fixture-driven, no network)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import SignalEvent
from app.signals.news_mispricing import news_in_window
from app.signals.unusual_flow import (
    ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
    UnusualFlowInput,
    evaluate_unusual_flow,
    unusual_flow_to_events,
)
from app.workers.tasks import run_unusual_flow_scan

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "news" / "unusual_flow_cases.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def test_news_in_window_is_shared_source_of_truth():
    """G03 and G04 must agree on "was there news in the window"."""
    anchor = _ts("2026-07-09T18:00:00Z")
    fresh = _ts("2026-07-09T17:52:00Z")
    stale = _ts("2026-07-09T12:00:00Z")

    assert news_in_window(fresh, now=anchor, window_sec=900) == (True, "fresh")
    assert news_in_window(stale, now=anchor, window_sec=900) == (False, "news_stale")

    # The anomaly evaluator is the exact inverse of the shared check.
    with_news = evaluate_unusual_flow(news_ts=fresh, occurred_ts=anchor, window_sec=900)
    assert with_news.emit is False
    assert with_news.reason == "news_catalyst_in_window"

    stale_news = evaluate_unusual_flow(news_ts=stale, occurred_ts=anchor, window_sec=900)
    assert stale_news.emit is True
    assert stale_news.reason == "news_stale"

    no_news = evaluate_unusual_flow(news_ts=None, occurred_ts=anchor, window_sec=900)
    assert no_news.emit is True
    assert no_news.reason == "no_news_found"


def test_fixture_cases_to_events():
    payload = _load()
    items = [
        UnusualFlowInput(
            market_slug=c["market_slug"],
            platform=c["platform"],
            kind=c["kind"],
            direction=c["direction"],
            magnitude=c["magnitude"],
            occurred_ts=_ts(c["occurred_ts"]),
            news_ts=_ts(c["news_ts"]) if c["news_ts"] else None,
            headline=c["headline"],
        )
        for c in payload["cases"]
    ]
    events = unusual_flow_to_events(items, window_sec=payload["window_sec"])

    expected_slugs = {
        c["market_slug"] for c in payload["cases"] if c["expect_emit"]
    }
    assert {e["market_id"] for e in events} == expected_slugs
    # Jump WITH fresh news must never emit an anomaly.
    assert "pm-will-lakers-beat-celtics" not in {e["market_id"] for e in events}

    for ev in events:
        assert ev["signal_type"] == ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE
        assert ev["payload"]["paper_trading_only"] is True
        assert ev["payload"]["catalyst"] == "none_found"
        # Neutral wording only — never an accusation.
        assert ev["payload"]["note"] == "No public catalyst found in the news window."
        blob = json.dumps(ev["payload"]).lower()
        for accusatory in ("insider", "manipulat", "illegal", "fraud", "suspicious"):
            assert accusatory not in blob


@pytest.mark.asyncio
async def test_scan_jump_with_news_emits_no_anomaly(db_session, monkeypatch):
    from app.signals.news_signal import NewsSignal

    now = datetime.now(UTC)
    _seed_market_and_jump(db_session, now)
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

    monkeypatch.setattr("app.signals.news_signal.fetch_news_signal", fake_fetch)

    result = await run_unusual_flow_scan(db_session)
    assert result["scanned"] == 1
    assert result["emitted"] == 0

    rows = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE
            )
        )
    ).all()
    assert list(rows) == []


@pytest.mark.asyncio
async def test_scan_jump_without_news_emits_anomaly(db_session, monkeypatch):
    now = datetime.now(UTC)
    _seed_market_and_jump(db_session, now)
    await db_session.flush()

    async def fake_fetch(topic: str, *, timeout: float = 30.0):
        return None  # no news found anywhere

    monkeypatch.setattr("app.signals.news_signal.fetch_news_signal", fake_fetch)

    result = await run_unusual_flow_scan(db_session)
    assert result["emitted"] == 1

    rows = list(
        (
            await db_session.scalars(
                select(SignalEvent).where(
                    SignalEvent.signal_type == ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE
                )
            )
        ).all()
    )
    assert len(rows) == 1
    event = rows[0]
    assert event.market_id == "pm-will-lakers-beat-celtics"
    assert event.payload["kind"] == "price_jump"
    assert event.payload["catalyst"] == "none_found"
    assert event.payload["paper_trading_only"] is True

    # Second pass dedupes: the same market is not flagged again.
    rerun = await run_unusual_flow_scan(db_session)
    assert rerun["emitted"] == 0


@pytest.mark.asyncio
async def test_task_respects_disabled_flag(monkeypatch):
    from app.core.config import get_settings
    from app.workers.tasks import unusual_flow_scan_task

    monkeypatch.setattr(get_settings(), "unusual_flow_enabled", False)
    result = await unusual_flow_scan_task({})
    assert result == {"scanned": 0, "emitted": 0, "skipped": "disabled"}


def _seed_market_and_jump(db_session, now: datetime) -> None:
    from app.db.models import Market, MarketStatus

    db_session.add(
        Market(
            slug="pm-will-lakers-beat-celtics",
            title="Will the Lakers beat the Celtics?",
            question="Will the Lakers beat the Celtics?",
            category="NBA",
            status=MarketStatus.OPEN,
            source="polymarket",
            volume=100000,
        )
    )
    db_session.add(
        SignalEvent(
            signal_type="delta:price_jump",
            platform="polymarket",
            market_id="pm-will-lakers-beat-celtics",
            headline_eligible=False,
            payload={
                "kind": "price_jump",
                "direction": "up",
                "magnitude": 0.08,
                "detail": {"prev": 0.5, "curr": 0.58, "bps": 800.0},
                "occurred_ts": (now - timedelta(minutes=3)).isoformat(),
            },
        )
    )
