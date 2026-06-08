"""Tests for LLM news feature extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.llm.news_features import NewsFeatures, extract_news_features


def _mock_completion(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_extract_news_features_parses_structured_response(monkeypatch):
    payload = (
        '{"injury_key_player": true, "back_to_back": true, '
        '"travel_flag": false, "extracted_text": "LeBron ruled out; B2B game."}'
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion(payload))
    monkeypatch.setattr(
        "app.llm.news_features.get_llm_client",
        lambda settings: mock_client,
    )

    settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="gem-test")
    result = await extract_news_features(
        "LeBron James ruled out for back-to-back vs Celtics",
        settings=settings,
    )

    assert isinstance(result, NewsFeatures)
    assert result.injury_key_player is True
    assert result.back_to_back is True
    assert result.travel_flag is False
    assert "LeBron" in result.extracted_text


@pytest.mark.asyncio
async def test_extract_news_features_heuristic_without_api_key():
    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="")
    result = await extract_news_features(
        "Star guard injured, team on back-to-back road trip",
        settings=settings,
    )
    assert result.injury_key_player is True
    assert result.back_to_back is True
    assert result.travel_flag is True


@pytest.mark.asyncio
async def test_extract_news_features_nullable_fields(monkeypatch):
    payload = (
        '{"injury_key_player": false, "back_to_back": null, '
        '"travel_flag": null, "extracted_text": "Routine practice day."}'
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion(payload))
    monkeypatch.setattr(
        "app.llm.news_features.get_llm_client",
        lambda settings: mock_client,
    )

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    result = await extract_news_features("Routine practice day.", settings=settings)
    assert result.injury_key_player is False
    assert result.back_to_back is None
    assert result.travel_flag is None
