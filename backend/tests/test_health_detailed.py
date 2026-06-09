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
async def test_detailed_health_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/detailed")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_detailed_health_paper_trading_only_true():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/detailed")
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_detailed_health_env_guard_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/detailed")
    assert response.json()["checks"]["env_guard"] == "ok"


@pytest.mark.asyncio
async def test_detailed_health_response_shape():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/detailed")
    body = response.json()
    assert body["status"] in {"ok", "degraded", "down"}
    assert isinstance(body["checks"], dict)
    assert body["checks"]["db"] in {"ok", "error"}
    assert body["checks"]["paper_orders_table"] in {"ok", "missing"}
    assert body["checks"]["users_table"] in {"ok", "missing"}
    assert body["checks"]["env_guard"] in {"ok", "FAIL"}
    assert body["version"] == "0.1.0"
