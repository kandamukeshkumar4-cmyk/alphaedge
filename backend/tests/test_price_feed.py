import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.models import OddsSnapshot
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.price_snapshot_seed import seed_price_snapshots
from app.workers.price_feed_worker import run_price_feed_once


@pytest.mark.asyncio
async def test_seed_price_snapshots_creates_ninety(db_session):
    inserted = await seed_price_snapshots(
        db_session,
        "nba-2025-01-15-lal-bos",
        end_price=0.65,
        n_points=90,
        step_sec=3600,
    )
    count = await db_session.scalar(
        select(func.count())
        .select_from(OddsSnapshot)
        .where(OddsSnapshot.market_slug == "nba-2025-01-15-lal-bos")
    )
    assert inserted == 90
    assert count == 90


@pytest.mark.asyncio
async def test_seed_price_snapshots_idempotent(db_session):
    slug = "nba-2025-01-15-lal-bos"
    await seed_price_snapshots(db_session, slug, end_price=0.65, n_points=90, step_sec=3600)
    await seed_price_snapshots(db_session, slug, end_price=0.65, n_points=90, step_sec=3600)
    count = await db_session.scalar(
        select(func.count()).select_from(OddsSnapshot).where(OddsSnapshot.market_slug == slug)
    )
    assert count == 90


@pytest.mark.asyncio
async def test_get_candles_returns_ninety_with_ohlcv_shape(db_session):
    service = MarketService(db_session)
    await service.seed_catalog_markets()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/markets/nba-2025-01-15-lal-bos/candles",
                params={"points": 90},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    candles = payload["candles"]
    assert len(candles) == 90
    for candle in candles:
        assert set(candle.keys()) == {"time", "open", "high", "low", "close"}
        assert candle["low"] <= candle["high"]


@pytest.mark.asyncio
async def test_get_candles_time_monotonically_increasing(db_session):
    service = MarketService(db_session)
    await service.seed_catalog_markets()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/markets/nba-2025-01-15-lal-bos/candles",
                params={"points": 90},
            )
    finally:
        app.dependency_overrides.clear()

    times = [candle["time"] for candle in response.json()["candles"]]
    assert times == sorted(times)
    assert len(set(times)) == len(times)


@pytest.mark.asyncio
async def test_run_price_feed_once_all_seed_returns_seed_skip(db_session, monkeypatch):
    from app.data.connectors import catalog_map

    all_seed = {
        slug: catalog_map.CatalogEntry(slug, "seed", spec_price=entry.spec_price)
        for slug, entry in catalog_map.CATALOG_MAP.items()
    }
    monkeypatch.setattr(catalog_map, "CATALOG_MAP", all_seed)
    monkeypatch.setattr("app.workers.price_feed_worker.CATALOG_MAP", all_seed)

    results = await run_price_feed_once(db_session)
    assert len(results) == 16
    assert all(status == "seed-skip" for status in results.values())


@pytest.mark.asyncio
async def test_get_candles_unknown_slug_returns_404(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/markets/not-a-real-slug/candles")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
