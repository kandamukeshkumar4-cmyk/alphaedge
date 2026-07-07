"""loop4 — provider registry, pure router, aggregation, graceful degradation.

Covers:
1. Registry: only providers with a configured key are registered (4 → 1 → 0).
2. Router: config-driven table, cap of 4, empty registry → empty.
3. aggregate(): known mean/stdev, single-model degrades, empty raises.
4. ensemble_forecast: flag OFF / 0 providers / all-fail all fall back to None;
   mixed success drops failures and aggregates survivors.

Never calls a real LLM — providers are stubbed / monkeypatched.
"""
from __future__ import annotations

import pytest

from app.forecasting.ensemble import aggregate
from app.forecasting.ensemble_providers import (
    EnsembleProvider,
    build_provider_registry,
    ensemble_forecast,
    route,
)


class FakeSettings:
    """Minimal settings surface used by build_provider_registry / ensemble_forecast."""

    llm_provider = "openai"
    llm_base_url = "https://api.openai.com/v1"
    llm_api_key = ""
    llm_model = "gpt-4o-mini"
    llm_model_analyst = ""
    nim_base_url = "https://nim.example/v1"
    nim_api_key = ""
    gemini_api_key = ""
    deepseek_base_url = "https://ds.example/v1"
    deepseek_api_key = ""
    deepseek_model = "deepseek-chat"
    kimi_base_url = "https://kimi.example/v1"
    kimi_api_key = ""
    kimi_model = "moonshot-v1-8k"
    glm_base_url = "https://glm.example/v1"
    glm_api_key = ""
    glm_model = "glm-4-flash"
    ensemble_enabled = True


def _settings(**overrides) -> FakeSettings:
    s = FakeSettings()
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


# ---------------------------------------------------------------------------
# 1. Registry — key presence controls registration (degradation chain)
# ---------------------------------------------------------------------------


def test_registry_no_keys_is_empty():
    assert build_provider_registry(_settings()) == []


def test_registry_only_primary_when_only_primary_key():
    reg = build_provider_registry(_settings(llm_api_key="sk-primary"))
    assert len(reg) == 1
    assert reg[0].route == ""  # primary route
    assert reg[0].model_id == "gpt-4o-mini"


def test_registry_missing_side_key_not_registered():
    # deepseek key present, kimi/glm absent -> primary + deepseek only
    reg = build_provider_registry(
        _settings(llm_api_key="sk-primary", deepseek_api_key="sk-ds")
    )
    names = {p.name for p in reg}
    assert "deepseek" in names
    assert "kimi" not in names
    assert "glm" not in names
    assert len(reg) == 2


def test_registry_all_four_when_all_keys_present():
    reg = build_provider_registry(
        _settings(
            llm_api_key="sk-primary",
            deepseek_api_key="sk-ds",
            kimi_api_key="sk-kimi",
            glm_api_key="sk-glm",
        )
    )
    assert len(reg) == 4
    assert {p.route for p in reg} == {"", "deepseek", "kimi", "glm"}


def test_registry_nim_primary_counts_when_nim_key_set():
    reg = build_provider_registry(_settings(llm_provider="nim", nim_api_key="nim-key"))
    assert len(reg) == 1
    assert reg[0].route == ""


# ---------------------------------------------------------------------------
# 2. Router — pure, config-driven, capped, empty-safe
# ---------------------------------------------------------------------------


def _providers(n: int) -> list[EnsembleProvider]:
    return [
        EnsembleProvider(name=f"p{i}", model_id=f"m{i}", route="", settings=None)
        for i in range(n)
    ]


def test_route_empty_registry_returns_empty():
    assert route("sports", []) == []


def test_route_sports_uses_all_capped_at_four():
    chosen = route("sports", _providers(6))
    assert len(chosen) == 4


def test_route_elections_uses_all():
    chosen = route("elections", _providers(3))
    assert len(chosen) == 3


def test_route_unknown_category_falls_back_to_default():
    chosen = route("who-knows", _providers(2))
    assert len(chosen) == 2


def test_route_none_category_uses_default():
    chosen = route(None, _providers(2))
    assert len(chosen) == 2


def test_route_respects_explicit_cap():
    chosen = route("sports", _providers(5), cap=2)
    assert len(chosen) == 2


def test_route_custom_table_numeric_policy():
    chosen = route("nba", _providers(4), table={"nba": "1", "default": "all"})
    assert len(chosen) == 1


# ---------------------------------------------------------------------------
# 3. aggregate() — known mean/stdev, single-model, empty
# ---------------------------------------------------------------------------


def test_aggregate_known_mean_and_stdev():
    result = aggregate([{"prob": 0.4, "provider": "a"}, {"prob": 0.6, "provider": "b"}])
    assert result["prob"] == pytest.approx(0.5)
    assert result["stdev"] == pytest.approx(0.1)
    assert result["n_models"] == 2
    assert result["spread_flag"] is False  # 0.1 <= 0.15


def test_aggregate_spread_flag_set_on_high_disagreement():
    result = aggregate([{"prob": 0.2, "provider": "a"}, {"prob": 0.8, "provider": "b"}])
    assert result["stdev"] == pytest.approx(0.3)
    assert result["spread_flag"] is True  # 0.3 > 0.15


def test_aggregate_single_model_degrades_cleanly():
    result = aggregate([{"prob": 0.65, "provider": "solo"}])
    assert result["prob"] == pytest.approx(0.65)
    assert result["stdev"] == 0.0
    assert result["n_models"] == 1
    assert result["spread_flag"] is False


def test_aggregate_empty_raises():
    with pytest.raises(ValueError, match="at least one"):
        aggregate([])


def test_aggregate_per_model_breakdown():
    result = aggregate(
        [
            {"prob": 0.4, "provider": "a", "rationale": "low"},
            {"prob": 0.6, "provider": "b", "rationale": "high"},
        ]
    )
    assert [m["provider"] for m in result["per_model"]] == ["a", "b"]
    assert result["per_model"][0]["rationale"] == "low"


# ---------------------------------------------------------------------------
# 4. ensemble_forecast — degradation chain (flag / 0 providers / all-fail)
# ---------------------------------------------------------------------------


class _StubProvider:
    """Stands in for EnsembleProvider without any network call."""

    def __init__(self, name: str, prob: float | None = None, fail: bool = False):
        self.name = name
        self._prob = prob
        self._fail = fail

    async def predict(self, question, context):
        if self._fail:
            raise RuntimeError(f"{self.name} unavailable")
        return {"prob": self._prob, "rationale": f"{self.name} says", "provider": self.name}


async def test_ensemble_forecast_disabled_returns_none():
    result = await ensemble_forecast("q", "ctx", _settings(ensemble_enabled=False))
    assert result is None


async def test_ensemble_forecast_no_providers_returns_none():
    # flag on but zero keys -> empty registry -> None (baseline fallback)
    result = await ensemble_forecast("q", "ctx", _settings(ensemble_enabled=True))
    assert result is None


async def test_ensemble_forecast_all_fail_returns_none(monkeypatch):
    import app.forecasting.ensemble_providers as ep

    monkeypatch.setattr(
        ep,
        "build_provider_registry",
        lambda s: [_StubProvider("a", fail=True), _StubProvider("b", fail=True)],
    )
    result = await ensemble_forecast("q", "ctx", _settings())
    assert result is None


async def test_ensemble_forecast_drops_failures_and_aggregates(monkeypatch):
    import app.forecasting.ensemble_providers as ep

    monkeypatch.setattr(
        ep,
        "build_provider_registry",
        lambda s: [
            _StubProvider("a", prob=0.4),
            _StubProvider("b", fail=True),  # dropped
            _StubProvider("c", prob=0.6),
        ],
    )
    result = await ensemble_forecast("q", "ctx", _settings())
    assert result is not None
    assert result["n_models"] == 2  # b dropped
    assert result["prob"] == pytest.approx(0.5)


async def test_ensemble_forecast_single_provider_degrades(monkeypatch):
    import app.forecasting.ensemble_providers as ep

    monkeypatch.setattr(
        ep, "build_provider_registry", lambda s: [_StubProvider("solo", prob=0.7)]
    )
    result = await ensemble_forecast("q", "ctx", _settings())
    assert result["n_models"] == 1
    assert result["stdev"] == 0.0
    assert result["prob"] == pytest.approx(0.7)


async def test_ensemble_forecast_timeout_is_dropped(monkeypatch):
    import asyncio

    import app.forecasting.ensemble_providers as ep

    class _SlowProvider:
        name = "slow"

        async def predict(self, question, context):
            await asyncio.sleep(1.0)
            return {"prob": 0.5, "provider": "slow"}

    monkeypatch.setattr(ep, "build_provider_registry", lambda s: [_SlowProvider()])
    result = await ensemble_forecast("q", "ctx", _settings(), timeout_s=0.01)
    assert result is None  # timed out -> dropped -> no survivors -> baseline
