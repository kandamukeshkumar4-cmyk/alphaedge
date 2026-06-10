import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.market_service import CATALOG_SLUGS, MarketService


@pytest.mark.asyncio
async def test_catalog_slugs_has_sixteen_markets():
    assert len(CATALOG_SLUGS) == 16


@pytest.mark.asyncio
async def test_seed_catalog_markets_creates_sixteen_idempotent(db_session):
    service = MarketService(db_session)
    first = await service.seed_catalog_markets()
    second = await service.seed_catalog_markets()

    assert len(first) == 16
    assert len(second) == 16
    assert {market.slug for market in first} == set(CATALOG_SLUGS)
    assert {market.slug for market in second} == set(CATALOG_SLUGS)


@pytest.mark.asyncio
async def test_list_markets_category_filter_crypto(db_session):
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
            response = await client.get("/api/v1/markets", params={"category": "Crypto"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    slugs = {market["slug"] for market in response.json()}
    assert slugs == {"crypto-btc-friday-5pm", "crypto-eth-100k-eoy"}


@pytest.mark.asyncio
async def test_list_markets_category_filter_culture(db_session):
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
            response = await client.get("/api/v1/markets", params={"category": "Culture"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    slugs = {market["slug"] for market in response.json()}
    assert slugs == {"culture-gta6-trailer", "culture-love-island-elim"}


@pytest.mark.asyncio
async def test_list_markets_category_filter_economics(db_session):
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
            response = await client.get("/api/v1/markets", params={"category": "Economics"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    slugs = {market["slug"] for market in response.json()}
    assert slugs == {"econ-cpi-above-3", "econ-fed-cut-march"}
