"""Loop117 — the market-detail chain for the WHOLE catalog (D1 + D5).

D1: ``/detail``, ``/prediction``, ``/explain`` and ``/agent-trace`` used to gate
on ``CATALOG_SLUGS`` (22 seed slugs), so every live-ingested polymarket/kalshi
market — ~98% of the catalog — returned ``404 Market not found``.

D5: ``/detail`` priced YES off the resting paper book with a hard-coded ``0.5``
fallback while ``/markets`` priced off the newest ``OddsSnapshot``, so the same
slug read 0.5 on the detail page and 0.65 on its own card.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import market_detail_cache
from app.db.models import OddsSnapshot
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

LIVE_SLUG = "pm-will-jesus-christ-return-before-2027"
SEED_SLUG = "nba-2025-01-15-lal-bos"
BARE_SLUG = "pm-catalog-row-without-any-price"


@pytest.fixture(autouse=True)
def _clear_detail_cache():
    market_detail_cache.invalidate()
    yield
    market_detail_cache.invalidate()


async def _make_market(db, slug: str, *, source: str, title: str):
    market = await MarketService(db).create_market(
        slug=slug,
        title=title,
        question=f"Will {title}?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        category="Culture",
        icon="*",
        volume=12_345,
        traders=42,
        market_count=1,
        description=f"Live-ingested mirror of {slug}.",
        resolution="Resolves YES per the source venue.",
    )
    market.source = source
    await db.flush()
    return market


async def _snapshot(db, slug: str, implied_yes: str):
    db.add(
        OddsSnapshot(
            market_slug=slug,
            implied_yes=Decimal(implied_yes),
            captured_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()


def _client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_detail_200_for_live_ingested_market(db_session):
    """D1: a polymarket-sourced catalog row is NOT a 404 on any of the four
    market-scoped read endpoints."""
    await _make_market(
        db_session, LIVE_SLUG, source="polymarket", title="Jesus Christ returns before 2027"
    )
    await _snapshot(db_session, LIVE_SLUG, "0.0300")

    try:
        async with _client(db_session) as client:
            detail = await client.get(f"/api/v1/markets/{LIVE_SLUG}/detail")
            prediction = await client.get(f"/api/v1/markets/{LIVE_SLUG}/prediction")
            explain = await client.get(f"/api/v1/markets/{LIVE_SLUG}/explain")
            trace = await client.get(f"/api/v1/markets/{LIVE_SLUG}/agent-trace")
    finally:
        app.dependency_overrides.clear()

    assert detail.status_code == 200, detail.text
    assert prediction.status_code == 200, prediction.text
    assert explain.status_code == 200, explain.text
    assert trace.status_code == 200, trace.text

    body = detail.json()
    assert body["slug"] == LIVE_SLUG
    assert body["title"] == "Jesus Christ returns before 2027"
    # Real stored data, not a seed default.
    assert body["price_source"] == "odds_snapshot"
    yes = next(o for o in body["outcomes"] if o["label"] == "YES")
    assert yes["price"] == pytest.approx(0.03)


@pytest.mark.asyncio
async def test_detail_price_matches_list_price(db_session):
    """D5: /detail, /markets/{slug} and /prediction all report ONE price.

    The paper order book is empty for this market — the old code fell back to a
    hard-coded 0.5 while the catalog row served the real 0.65.
    """
    await _make_market(db_session, SEED_SLUG, source="seed", title="Lakers vs Celtics")
    # 0.71 deliberately differs from the bundled CATALOG_MAP spec price (0.65),
    # so a pass proves the snapshot store (not the seed spec) is the source.
    await _snapshot(db_session, SEED_SLUG, "0.7100")

    try:
        async with _client(db_session) as client:
            detail = await client.get(f"/api/v1/markets/{SEED_SLUG}/detail")
            catalog = await client.get(f"/api/v1/markets/{SEED_SLUG}")
            latest = await client.get(f"/api/v1/markets/{SEED_SLUG}/prices/latest")
            prediction = await client.get(f"/api/v1/markets/{SEED_SLUG}/prediction")
            explain = await client.get(f"/api/v1/markets/{SEED_SLUG}/explain")
    finally:
        app.dependency_overrides.clear()

    assert detail.status_code == 200, detail.text
    assert catalog.status_code == 200, catalog.text

    list_price = float(catalog.json()["yes_price"])
    detail_yes = next(o for o in detail.json()["outcomes"] if o["label"] == "YES")
    detail_no = next(o for o in detail.json()["outcomes"] if o["label"] == "NO")

    assert list_price == pytest.approx(0.71)
    assert detail_yes["price"] == pytest.approx(list_price)
    assert detail_yes["implied_prob"] == pytest.approx(list_price)
    assert detail_no["price"] == pytest.approx(round(1.0 - list_price, 4))
    assert float(latest.json()["yes"]) == pytest.approx(list_price)

    # The edge chain must score against the SAME number, not 0.5.
    assert prediction.json()["market_implied"] == pytest.approx(list_price)
    assert explain.json()["market_implied"] == pytest.approx(list_price)


@pytest.mark.asyncio
async def test_prediction_absent_is_honest_not_404(db_session):
    """A catalog row with no stored price and no logged forecast answers 200
    with an honest 'no prediction available' body — never a 404, never 0.5."""
    await _make_market(
        db_session, BARE_SLUG, source="polymarket", title="Catalog row without a price"
    )

    try:
        async with _client(db_session) as client:
            prediction = await client.get(f"/api/v1/markets/{BARE_SLUG}/prediction")
            explain = await client.get(f"/api/v1/markets/{BARE_SLUG}/explain")
            trace = await client.get(f"/api/v1/markets/{BARE_SLUG}/agent-trace")
            detail = await client.get(f"/api/v1/markets/{BARE_SLUG}/detail")
            missing = await client.get("/api/v1/markets/not-in-the-catalog-at-all/prediction")
    finally:
        app.dependency_overrides.clear()

    assert prediction.status_code == 200, prediction.text
    body = prediction.json()
    assert body["available"] is False
    assert body["predicted_prob"] is None
    assert body["edge"] is None
    assert body["market_implied"] is None
    assert body["price_source"] == "unavailable"
    assert "no prediction available" in body["reason"]

    assert explain.status_code == 200
    assert explain.json()["available"] is False
    assert explain.json()["model_prob"] is None

    assert trace.status_code == 200
    assert trace.json()["available"] is False
    assert trace.json()["steps"] == []

    # Detail still answers, with an honest null price rather than a fake 0.5.
    assert detail.status_code == 200
    assert detail.json()["price_source"] == "unavailable"
    assert all(o["price"] is None for o in detail.json()["outcomes"])
    assert detail.json()["forecast"] is None

    # A slug the catalog genuinely does not list is still a 404.
    assert missing.status_code == 404
