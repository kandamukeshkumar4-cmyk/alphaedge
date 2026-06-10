"""Tests for GET /api/v1/markets category/sort/q filtering."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
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
