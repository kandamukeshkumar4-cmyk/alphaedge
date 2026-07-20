"""Loop V78 (N1) — /api/v1/signals/feed display enrichment.

The alert card needs real stored market context: market title, category, icon
glyph, venue image url, volume/traders/market_count, and up-to-two outcome rows
priced from the latest stored OddsSnapshot. Honest-omission rules: an
unmirrored slug yields all-None enrichment and no outcomes; a market with no
odds snapshot yields no outcome rows (never an invented price).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import signal_feed_cache
from app.db.models import Market, OddsSnapshot, SignalEvent
from app.db.session import get_db
from app.main import app

VENUE_IMAGE = (
    "https://polymarket-upload.s3.us-east-2.amazonaws.com/elon-musk-abc123.jpg"
)


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    signal_feed_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    signal_feed_cache.invalidate()


async def _get(path: str = "/api/v1/signals/feed"):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def _event(market_id: str, *, minutes_ago: int = 1) -> SignalEvent:
    return SignalEvent(
        id=uuid4(),
        signal_type="delta:price_jump",
        platform="polymarket",
        market_id=market_id,
        headline_eligible=True,
        payload={"market_name": market_id, "sample_size": 10},
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


async def _seed_market(db_session, slug: str) -> Market:
    market = Market(
        id=uuid4(),
        slug=slug,
        title="Will Elon Musk post 100 times this week?",
        question="Will Elon Musk post 100 times this week?",
        category="Culture",
        icon="🐦",
        volume=52_617_317,
        traders=1_234,
        market_count=38,
        image_url=VENUE_IMAGE,
    )
    db_session.add(market)
    await db_session.flush()
    return market


async def _seed_snapshot(
    db_session, slug: str, implied_yes: str, *, minutes_ago: int
) -> None:
    db_session.add(
        OddsSnapshot(
            id=uuid4(),
            market_slug=slug,
            implied_yes=Decimal(implied_yes),
            source="polymarket.gamma",
            captured_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_feed_enriches_with_stored_market_and_outcomes(db_session):
    slug = "pm-musk-posts-week"
    await _seed_market(db_session, slug)
    # Two snapshots: the LATEST one must win.
    await _seed_snapshot(db_session, slug, "0.3500", minutes_ago=30)
    await _seed_snapshot(db_session, slug, "0.3900", minutes_ago=5)
    db_session.add(_event(slug))
    await db_session.flush()

    response = await _get()
    assert response.status_code == 200
    item = next(s for s in response.json()["signals"] if s["market_id"] == slug)

    assert item["market_title"] == "Will Elon Musk post 100 times this week?"
    assert item["category"] == "Culture"
    assert item["icon"] == "🐦"
    assert item["image_url"] == VENUE_IMAGE
    assert item["volume"] == 52_617_317
    assert item["traders"] == 1_234
    assert item["market_count"] == 38

    outcomes = item["outcomes"]
    assert [o["name"] for o in outcomes] == ["Yes", "No"]
    assert outcomes[0]["price"] == pytest.approx(0.39)
    assert outcomes[0]["image_url"] == VENUE_IMAGE
    assert outcomes[1]["price"] == pytest.approx(0.61)
    # NO row carries no image — the UI falls back to the glyph token.
    assert outcomes[1]["image_url"] is None


@pytest.mark.asyncio
async def test_feed_omits_enrichment_for_unmirrored_slug(db_session):
    slug = "orphan-no-such-market"
    db_session.add(_event(slug))
    await db_session.flush()

    response = await _get()
    assert response.status_code == 200
    item = next(s for s in response.json()["signals"] if s["market_id"] == slug)

    assert item["market_title"] is None
    assert item["category"] is None
    assert item["icon"] is None
    assert item["image_url"] is None
    assert item["volume"] is None
    assert item["traders"] is None
    assert item["market_count"] is None
    assert item["outcomes"] == []


@pytest.mark.asyncio
async def test_feed_omits_outcomes_when_no_snapshot(db_session):
    slug = "pm-no-snapshots-yet"
    await _seed_market(db_session, slug)
    db_session.add(_event(slug))
    await db_session.flush()

    response = await _get()
    assert response.status_code == 200
    item = next(s for s in response.json()["signals"] if s["market_id"] == slug)

    # Market context still enriches; outcome rows are honestly omitted.
    assert item["market_title"] == "Will Elon Musk post 100 times this week?"
    assert item["outcomes"] == []
