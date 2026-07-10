"""J03 — GET /api/v1/system/model-ab readout (analysis only, never flips model)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app


async def _get_model_ab(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/api/v1/system/model-ab")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_model_ab_below_threshold_reports_not_ready(db_session):
    """Empty DB → resolved_count 0 < 100 → ready=false, honest progress, never 500."""
    resp = await _get_model_ab(db_session)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is False
    assert body["resolved_count"] == 0
    assert body["threshold"] == 100
    assert body["applied"] is False
    assert body["model_default"] == get_settings().ml_model_type
    # lightgbm_available is a real boolean either way — never fabricated.
    assert isinstance(body["lightgbm_available"], bool)


@pytest.mark.asyncio
async def test_model_ab_never_reports_applied_true(db_session):
    """The harness is analysis-only: `applied` must never be true, and the
    deployed default model must be unchanged after the call."""
    before = get_settings().ml_model_type
    resp = await _get_model_ab(db_session)
    assert resp.status_code == 200
    assert resp.json()["applied"] is False
    assert get_settings().ml_model_type == before
