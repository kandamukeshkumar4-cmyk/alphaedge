"""Tests for the market explainer / AI advisor endpoint (Loop R)."""

from __future__ import annotations

import pytest

VALID_SLUG = "nba-2025-01-15-lal-bos"
UNKNOWN_SLUG = "not-a-real-market-slug"


@pytest.mark.asyncio
async def test_explainer_unknown_slug_returns_404(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{UNKNOWN_SLUG}/explain")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_explainer_returns_deterministic_advisor_fields(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_used"] == "deterministic"
    assert payload["slug"] == VALID_SLUG
    assert "trade_rationale" in payload
    assert "edge" in payload
    assert payload["confidence_label"] in {"Weak", "Moderate", "Strong"}


@pytest.mark.asyncio
async def test_explainer_paper_trading_only_true(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_explainer_response_has_all_fields(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{VALID_SLUG}/explain")

    assert response.status_code == 200
    payload = response.json()
    for key in (
        "slug",
        "available",
        "model_prob",
        "market_implied",
        "edge",
        "edge_direction",
        "confidence_label",
        "news_signals",
        "trade_rationale",
        "provisional",
        "price_source",
        "paper_trading_only",
    ):
        assert key in payload
    assert payload["slug"] == VALID_SLUG
    assert isinstance(payload["news_signals"], list)
