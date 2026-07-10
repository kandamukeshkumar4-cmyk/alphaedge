"""Audit H-SEC-03 / M-SEC-01: compute-heavy endpoints must not run anonymously
(LLM cost abuse, market auto-create pollution, sync replay DoS)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_analyst_run_requires_auth(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/analyst/run?market_slug=pm-anything")
    app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backtest_run_requires_auth(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/backtest/run",
            json={
                "market_slug": "nba-2025-01-15-lal-bos",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-02T00:00:00Z",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
