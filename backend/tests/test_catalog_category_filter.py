import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.market_service import CATALOG_SLUGS, MarketService


@pytest.mark.asyncio
async def test_seed_catalog_markets_populates_all_eight_slugs(db_session):
    service = MarketService(db_session)
    seeded = await service.seed_catalog_markets()

    assert len(seeded) == 8
    assert {market.slug for market in seeded} == set(CATALOG_SLUGS)


@pytest.mark.asyncio
async def test_seed_catalog_markets_uses_loop_l_categories(db_session):
    service = MarketService(db_session)
    seeded = await service.seed_catalog_markets()

    categories = {market.category for market in seeded}
    assert {"NBA", "FIFA WC2026", "Elections"}.issubset(categories)


@pytest.mark.asyncio
async def test_list_markets_category_filter_nba(db_session):
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
            response = await client.get("/api/v1/markets", params={"category": "NBA"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    slugs = {market["slug"] for market in response.json()}
    assert slugs == {"nba-2025-01-15-lal-bos"}


@pytest.mark.asyncio
async def test_list_markets_category_filter_fifa_wc2026(db_session):
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
            response = await client.get("/api/v1/markets", params={"category": "FIFA WC2026"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    slugs = {market["slug"] for market in response.json()}
    assert slugs == {
        "wc2026-m1-mex-homewin",
        "wc2026-m1-draw",
        "wc2026-m1-rsa-awaywin",
        "wc2026-winner-brazil",
        "wc2026-winner-france",
        "wc2026-winner-argentina",
    }


@pytest.mark.asyncio
async def test_list_markets_category_filter_elections(db_session):
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
            response = await client.get("/api/v1/markets", params={"category": "Elections"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    slugs = {market["slug"] for market in response.json()}
    assert slugs == {"elect-la-mayor-2026"}


@pytest.mark.asyncio
async def test_list_markets_rejects_invalid_category(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/markets", params={"category": "Crypto"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
