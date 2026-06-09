import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.market_service import CATALOG_SLUGS

REQUIRED_FIELDS = (
    "slug",
    "predicted_prob",
    "confidence",
    "edge",
    "is_edge",
    "reason",
    "provisional",
    "paper_trading_only",
)

NBA_SLUG = "nba-2025-01-15-lal-bos"
FIFA_SLUG = "wc2026-m1-mex-homewin"


@pytest.mark.asyncio
async def test_unknown_slug_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/markets/unknown-market-slug/prediction")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_valid_nba_slug_returns_prediction():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{NBA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_trading_only"] is True
    assert 0.0 <= payload["predicted_prob"] <= 1.0


@pytest.mark.asyncio
async def test_valid_fifa_slug_is_provisional():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{FIFA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provisional"] is True


@pytest.mark.asyncio
async def test_response_has_all_required_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{NBA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    for field in REQUIRED_FIELDS:
        assert field in payload


@pytest.mark.asyncio
async def test_provisional_markets_have_no_edge():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for slug in sorted(CATALOG_SLUGS):
            response = await client.get(f"/api/v1/markets/{slug}/prediction")
            assert response.status_code == 200
            payload = response.json()
            if payload["provisional"]:
                assert payload["is_edge"] is False
