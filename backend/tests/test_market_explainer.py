"""Tests for the market explainer endpoint (Loop H)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

VALID_SLUG = "nba-2025-01-15-lal-bos"
UNKNOWN_SLUG = "not-a-real-market-slug"


@pytest.mark.asyncio
async def test_explainer_unknown_slug_returns_404():
    """Slug not in CATALOG_SLUGS should return 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{UNKNOWN_SLUG}/explain")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_explainer_no_api_key_returns_graceful_response(monkeypatch):
    """When ANTHROPIC_API_KEY is absent the endpoint should still return 200
    with model_used == 'none' and a human-readable explanation."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_used"] == "none"
    explanation = payload["explanation"].lower()
    assert "unavailable" in explanation or "anthropic_api_key" in explanation


@pytest.mark.asyncio
async def test_explainer_paper_trading_only_true(monkeypatch):
    """Any valid slug must always return paper_trading_only == True."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_explainer_response_has_all_fields(monkeypatch):
    """Response must contain slug, explanation, model_used, and paper_trading_only."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    payload = response.json()
    assert "slug" in payload
    assert "explanation" in payload
    assert "model_used" in payload
    assert "paper_trading_only" in payload
    assert payload["slug"] == VALID_SLUG
