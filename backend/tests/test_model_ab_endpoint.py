"""Public A/B GET is read-only; it never trains the comparison itself."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app


@pytest.mark.asyncio
async def test_model_ab_returns_controlled_cache_miss_without_training(db_session, monkeypatch):
    async def override_get_db():
        yield db_session

    async def must_not_refresh(_session):  # pragma: no cover - guard
        raise AssertionError("public GET must not refresh/train the A/B")

    monkeypatch.setattr("app.ml.ab_harness.refresh_controlled_ab_readout", must_not_refresh)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/model-ab")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["dataset_source"] == "forecast_scores"
    assert body["note"] == "controlled_readout_not_refreshed"
    assert body["applied"] is False
