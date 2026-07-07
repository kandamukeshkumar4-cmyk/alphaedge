"""Tests for LLM prediction explanation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.llm.explain import explain_prediction


def _mock_completion(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_explain_prediction_returns_string(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_completion(
            "The model gives the Lakers a 58% chance, slightly above the market implied 55%."
        )
    )
    monkeypatch.setattr(
        "app.llm.explain.resolve_routed_client",
        lambda settings, route, *, use_case_model="": (mock_client, "test-model"),
    )

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    result = await explain_prediction(
        market_slug="nba-2025-01-15-lal-bos",
        predicted_prob=0.58,
        edge=0.03,
        news_headline="LeBron returns from rest",
        settings=settings,
    )

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_explain_prediction_heuristic_without_api_key():
    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="")
    result = await explain_prediction(
        market_slug="nba-2025-01-15-lal-bos",
        predicted_prob=0.65,
        edge=0.05,
        news_headline="Star player questionable",
        settings=settings,
    )
    assert "65" in result  # "65.0%" from :.1% format
    assert "Heuristic" in result


@pytest.mark.asyncio
async def test_explain_prediction_does_not_contain_stake_or_side(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_completion("Model probability is 0.72; edge is +0.07.")
    )
    monkeypatch.setattr(
        "app.llm.explain.resolve_routed_client",
        lambda settings, route, *, use_case_model="": (mock_client, "test-model"),
    )

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    result = await explain_prediction(
        market_slug="nba-test",
        predicted_prob=0.72,
        edge=0.07,
        news_headline="",
        settings=settings,
    )
    # The LLM response is passed through as-is — verify no bet decision words leaked in
    assert isinstance(result, str)
    lower = result.lower()
    assert "bet" not in lower or "do not bet" in lower  # explanation only, no instruction
