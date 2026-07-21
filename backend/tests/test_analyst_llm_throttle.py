"""H5 — NIM concurrency / 503 retry for analyst write_brief."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(_env_file=None, PAPER_TRADING_ONLY=True, LLM_API_KEY="k", LLM_PROVIDER="openai")
    base.update(overrides)
    return Settings(**base)


def _ok_response(content: str = "LLM headline\nLLM body from retry."):
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
async def test_write_brief_retries_once_on_503_then_succeeds(monkeypatch):
    """First call 503 → sleep + retry → LLM brief (generator != fallback)."""
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    calls: list[str] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append("create")
            if len(calls) == 1:
                raise RuntimeError(
                    "503 ResourceExhausted: Worker local total request limit reached (39/32)"
                )
            return _ok_response()

    class _Client:
        class chat:  # noqa: N801
            completions = _Completions()

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(analyst_mod.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_Client(), "nvidia/nemotron-3-ultra-550b-a55b"),
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
    assert result.headline == "LLM headline"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_write_brief_falls_back_after_two_503s(monkeypatch):
    """Always-503 stub → fallback brief; create called exactly twice."""
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    calls: list[str] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append("create")
            raise RuntimeError(
                "503 ResourceExhausted: Worker local total request limit reached (39/32)"
            )

    class _Client:
        class chat:  # noqa: N801
            completions = _Completions()

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(analyst_mod.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(
        provider_mod,
        "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_Client(), "nvidia/nemotron-3-ultra-550b-a55b"),
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
    assert result.generator == "fallback"
    assert len(calls) == 2
