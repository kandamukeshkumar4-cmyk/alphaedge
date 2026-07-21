"""B0 — LLM briefs stamp model_version with the resolved model_id."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(_env_file=None, PAPER_TRADING_ONLY=True, LLM_API_KEY="k", LLM_PROVIDER="openai")
    base.update(overrides)
    return Settings(**base)


def _ok_response(content: str = "LLM headline\nLLM body with model stamp."):
    class _Msg:
        pass

    msg = _Msg()
    msg.content = content

    class _Choice:
        message = msg

    class _Resp:
        choices = [_Choice()]

    return _Resp()


@pytest.mark.asyncio
async def test_llm_brief_stamps_model_version(monkeypatch):
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    stub_model_id = "nvidia/nemotron-3-ultra-550b-a55b"

    class _Completions:
        async def create(self, **kwargs):
            return _ok_response()

    class _Client:
        class chat:  # noqa: N801
            completions = _Completions()

    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_Client(), stub_model_id),
    )
    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_endpoint",
        lambda s, route: ("https://example.invalid/v1", "k"),
    )

    state = analyst_mod.AnalystState(market_slug="nba-2025-01-15-lal-bos")
    state.market_state = {"title": "Lakers vs Celtics", "implied_yes": 0.55}
    state.evidence = {"model": {"predicted_prob": 0.55, "edge": 0.0}}

    result = await analyst_mod.write_brief(state, _settings())
    assert result.generator == "llm"
    assert result.model_version == stub_model_id
