"""P1 — LLM planner fallback for scanner compile (stubbed client)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.services.scanner_compiler_service import (
    compile_scanner_flow,
    compile_scanner_spec,
    is_valid_compiled_spec,
)


def _mock_completion(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _valid_llm_spec() -> dict:
    return {
        "name": "NBA whale scan",
        "universe": {"categories": ["nba", "sports"], "minimum_volume": 1000},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": False,
            "interval_minutes": 30,
        },
        "steps": [
            {"type": "WHALE_FLOW"},
            {"type": "PRICE_TREND", "window_days": 7},
        ],
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
        "limit": 10,
        "notes": [],
    }


@pytest.mark.asyncio
async def test_valid_llm_spec_accepted(monkeypatch):
    """When notes remain and LLM returns a whitelist-valid spec, use llm-assisted."""
    text = "xyzzy plugh frobozz"  # leaves notes; deterministic has empty steps
    det = compile_scanner_spec(text)
    assert det["notes"]  # precondition: planner path engaged

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_completion(json.dumps(_valid_llm_spec()))
    )
    monkeypatch.setattr(
        "app.llm.provider.resolve_routed_client",
        lambda settings, route, *, use_case_model="": (mock_client, "test-model"),
    )
    # Also patch where the compiler imports it at call time
    monkeypatch.setattr(
        "app.services.scanner_compiler_service.resolve_routed_client",
        lambda settings, route, *, use_case_model="": (mock_client, "test-model"),
        raising=False,
    )

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    # Patch resolve inside _llm_plan_spec import path
    import app.llm.provider as provider_mod

    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_client",
        lambda settings, route, *, use_case_model="": (mock_client, "test-model"),
    )
    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_endpoint",
        lambda settings, route: ("https://api.openai.com/v1", "sk-test"),
    )

    result = await compile_scanner_flow(text, settings)
    assert result["compiler"] == "llm-assisted"
    assert result["spec"]["steps"][0]["type"] == "WHALE_FLOW"
    assert is_valid_compiled_spec(result["spec"])
    mock_client.chat.completions.create.assert_awaited()
    call_kwargs = mock_client.chat.completions.create.await_args.kwargs
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["max_tokens"] == 800


@pytest.mark.asyncio
async def test_invalid_step_type_falls_back_to_deterministic(monkeypatch):
    text = "xyzzy plugh frobozz"
    det = compile_scanner_spec(text)
    bad = _valid_llm_spec()
    bad["steps"] = [{"type": "NOT_A_REAL_STEP"}]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_completion(json.dumps(bad))
    )
    import app.llm.provider as provider_mod

    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_client",
        lambda settings, route, *, use_case_model="": (mock_client, "test-model"),
    )
    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_endpoint",
        lambda settings, route: ("https://api.openai.com/v1", "sk-test"),
    )

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    result = await compile_scanner_flow(text, settings)
    assert result["compiler"] == "deterministic"
    assert result["spec"] == det
    assert not is_valid_compiled_spec(bad)


@pytest.mark.asyncio
async def test_no_llm_config_path_unchanged():
    text = "xyzzy plugh frobozz"
    det = compile_scanner_spec(text)
    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="")
    result = await compile_scanner_flow(text, settings)
    assert result["compiler"] == "deterministic"
    assert result["spec"] == det

    # Also: no settings at all
    result2 = await compile_scanner_flow(text, None)
    assert result2["compiler"] == "deterministic"
    assert result2["spec"] == det
