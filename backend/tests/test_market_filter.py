"""Tests for GET /api/v1/markets category/sort/q filtering."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.db.models import MarketStatus, OddsSnapshot
from app.main import app
from app.services.market_service import MarketService


async def _seed(db_session):
    svc = MarketService(db_session)
    base = datetime.now(timezone.utc) + timedelta(days=1)
    await svc.create_market(
        slug="nba-test-game",
        title="NBA Test Game",
        question="Will team A win?",
        category="NBA",
        volume=5000,
        traders=100,
        lock_at=base,
    )
    await svc.create_market(
        slug="crypto-btc-test",
        title="Bitcoin Price Test",
        question="Will BTC hit 100k?",
        category="Crypto",
        volume=3000,
        traders=200,
        lock_at=base,
    )
    await svc.create_market(
        slug="elect-test-vote",
        title="Election Vote Test",
        question="Who wins?",
        category="Elections",
        volume=1000,
        traders=50,
        lock_at=base,
    )


def _override(db_session):
    async def _get_db():
        yield db_session

    return _get_db


@pytest.mark.asyncio
async def test_filter_by_sports_category_returns_nba(db_session):
    await _seed(db_session)
    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/markets?category=sports")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    slugs = [m["slug"] for m in resp.json()]
    assert "nba-test-game" in slugs
    assert "crypto-btc-test" not in slugs


@pytest.mark.asyncio
async def test_filter_by_crypto_category(db_session):
    await _seed(db_session)
    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/markets?category=crypto")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    slugs = [m["slug"] for m in resp.json()]
    assert "crypto-btc-test" in slugs
    assert "nba-test-game" not in slugs


@pytest.mark.asyncio
async def test_sort_by_traders_descending(db_session):
    await _seed(db_session)
    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/markets?sort=traders")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    markets = resp.json()
    assert len(markets) >= 3
    traders_list = [m["traders"] for m in markets[:3]]
    assert traders_list == sorted(traders_list, reverse=True)


@pytest.mark.asyncio
async def test_sort_active_ranks_recent_movement_and_excludes_decided(db_session):
    svc = MarketService(db_session)
    now = datetime.now(timezone.utc)
    moving = await svc.create_market(
        slug="active-moving",
        title="Active moving",
        question="Moving?",
        volume=1_000,
        lock_at=now + timedelta(days=2),
    )
    flat = await svc.create_market(
        slug="active-flat-high-volume",
        title="Active flat",
        question="Flat?",
        volume=1_000_000,
        lock_at=now + timedelta(days=1),
    )
    resolved = await svc.create_market(
        slug="active-resolved",
        title="Resolved",
        question="Resolved?",
        volume=2_000_000,
        lock_at=now + timedelta(days=1),
    )
    resolved.status = MarketStatus.RESOLVED
    decided = await svc.create_market(
        slug="active-decided-price",
        title="Decided price",
        question="Decided?",
        volume=3_000_000,
        lock_at=now + timedelta(days=1),
    )
    past_close = await svc.create_market(
        slug="active-past-close",
        title="Past close",
        question="Closed?",
        volume=4_000_000,
        lock_at=now - timedelta(minutes=1),
    )
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=moving.slug,
                implied_yes=Decimal("0.40"),
                captured_at=now - timedelta(hours=4),
            ),
            OddsSnapshot(
                market_slug=moving.slug,
                implied_yes=Decimal("0.62"),
                captured_at=now - timedelta(minutes=5),
            ),
            OddsSnapshot(
                market_slug=flat.slug,
                implied_yes=Decimal("0.55"),
                captured_at=now - timedelta(hours=4),
            ),
            OddsSnapshot(
                market_slug=flat.slug,
                implied_yes=Decimal("0.56"),
                captured_at=now - timedelta(minutes=4),
            ),
            OddsSnapshot(
                market_slug=resolved.slug,
                implied_yes=Decimal("0.50"),
                captured_at=now - timedelta(minutes=3),
            ),
            OddsSnapshot(
                market_slug=decided.slug,
                implied_yes=Decimal("0.005"),
                captured_at=now - timedelta(minutes=2),
            ),
            OddsSnapshot(
                market_slug=past_close.slug,
                implied_yes=Decimal("0.50"),
                captured_at=now - timedelta(minutes=1),
            ),
        ]
    )
    await db_session.flush()

    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/markets?sort=active")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    slugs = [m["slug"] for m in resp.json()]
    assert slugs == ["active-moving", "active-flat-high-volume"]


@pytest.mark.asyncio
async def test_search_by_title_q(db_session):
    await _seed(db_session)
    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/markets?q=Bitcoin")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert all("bitcoin" in m["title"].lower() for m in results)


@pytest.mark.asyncio
async def test_invalid_category_returns_400(db_session):
    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/markets?category=notacategory")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
