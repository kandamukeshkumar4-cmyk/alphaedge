"""Tests for LLM resolution matching assist."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.llm.resolution_matcher import ResolutionMatch, llm_resolution_verdict


def _mock_completion(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_llm_resolution_verdict_parses_structured_response(monkeypatch):
    payload = (
        '{"is_match": true, "confidence": 0.92, '
        '"rationale": "Both describe Lakers vs Celtics on Jan 15."}'
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion(payload))
    monkeypatch.setattr(
        "app.llm.resolution_matcher.get_llm_client",
        lambda settings: mock_client,
    )

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    result = await llm_resolution_verdict(
        "Will the Lakers beat the Celtics?",
        "NBA: Lakers @ Celtics, January 15",
        settings=settings,
    )

    assert isinstance(result, ResolutionMatch)
    assert result.is_match is True
    assert result.confidence == pytest.approx(0.92)
    assert "Lakers" in result.rationale


@pytest.mark.asyncio
async def test_llm_resolution_verdict_heuristic_without_api_key():
    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="")
    result = await llm_resolution_verdict(
        "Lakers beat Celtics",
        "Lakers beat Celtics tonight",
        settings=settings,
    )
    assert result.is_match is True
    assert result.confidence == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_llm_resolution_verdict_clamps_confidence(monkeypatch):
    payload = '{"is_match": false, "confidence": 1.5, "rationale": "unrelated"}'
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion(payload))
    monkeypatch.setattr(
        "app.llm.resolution_matcher.get_llm_client",
        lambda settings: mock_client,
    )

    settings = Settings(LLM_PROVIDER="nim", NIM_API_KEY="nv-test")
    result = await llm_resolution_verdict("A", "B", settings=settings)
    assert result.confidence == 1.0
