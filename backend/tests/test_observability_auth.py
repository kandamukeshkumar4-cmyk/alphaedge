"""Audit H-SEC-01: every /api/v1/admin/observability/* route must require the
admin API key — traces leak agent-run step input/output data."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app

ROUTES = [
    "/api/v1/admin/observability/traces",
    "/api/v1/admin/observability/drift",
    "/api/v1/admin/observability/slo",
    "/api/v1/admin/observability/summary",
]


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
async def test_observability_rejects_missing_admin_key(db_session, route):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(route)
    app.dependency_overrides.clear()

    assert response.status_code == 422  # required X-Admin-API-Key header absent


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
async def test_observability_rejects_wrong_admin_key(db_session, route):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(route, headers={"X-Admin-API-Key": "wrong-key"})
    app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_observability_traces_accepts_valid_admin_key(db_session):
    from app.core.config import get_settings

    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/observability/traces",
            headers={"X-Admin-API-Key": get_settings().admin_api_key},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
