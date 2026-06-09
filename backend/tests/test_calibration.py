import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_calibration_latest_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_calibration_paper_trading_only_is_true():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_calibration_response_has_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "brier_score",
        "calibration_error",
        "markets_evaluated",
        "last_updated",
        "gate",
        "paper_trading_only",
    }


@pytest.mark.asyncio
async def test_calibration_no_resolved_markets_returns_no_data():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["gate"] == "no-data"
    assert body["markets_evaluated"] == 0
