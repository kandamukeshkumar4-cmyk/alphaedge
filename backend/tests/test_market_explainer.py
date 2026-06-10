"""Tests for the market explainer / AI advisor endpoint (Loop R)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

VALID_SLUG = "nba-2025-01-15-lal-bos"
UNKNOWN_SLUG = "not-a-real-market-slug"


@pytest.mark.asyncio
async def test_explainer_unknown_slug_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{UNKNOWN_SLUG}/explain")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_explainer_returns_deterministic_advisor_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_used"] == "deterministic"
    assert payload["slug"] == VALID_SLUG
    assert "trade_rationale" in payload
    assert "edge" in payload
    assert payload["confidence_label"] in {"Weak", "Moderate", "Strong"}


@pytest.mark.asyncio
async def test_explainer_paper_trading_only_true():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_explainer_response_has_all_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    payload = response.json()
    for key in (
        "slug",
        "model_prob",
        "market_implied",
        "edge",
        "edge_direction",
        "confidence_label",
        "news_signals",
        "trade_rationale",
        "provisional",
        "paper_trading_only",
    ):
        assert key in payload
    assert payload["slug"] == VALID_SLUG
    assert isinstance(payload["news_signals"], list)
