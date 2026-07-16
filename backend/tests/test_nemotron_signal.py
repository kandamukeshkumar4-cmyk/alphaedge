"""Loop V52 — Nemotron reasoning signal (mock NIM; flag/key/leakage guards)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.graph import GRAPH_NODES, nemotron_node, run_agent_graph
from app.agents.clone_service import VETTED_NODE_NAMES
from app.signals.nemotron_signal import (
    NemotronSignal,
    assert_pre_close_only,
    cache_signal,
    clear_cache,
    fetch_nemotron_signal,
    reset_circuit_breaker,
)


@pytest.fixture(autouse=True)
def _clean_nemotron_state():
    clear_cache()
    reset_circuit_breaker()
    yield
    clear_cache()
    reset_circuit_breaker()


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "nemotron_signal_enabled": True,
        "nim_api_key": "nvapi-test",
        "nim_base_url": "https://integrate.api.nvidia.com/v1",
        "nemotron_model": "nvidia/nemotron-3-nano-30b-a3b",
        "nemotron_prompt_version": "v1",
        "nemotron_signal_timeout": 5.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str = "", fail_once: bool = False, calls: list | None = None):
        self.content = content
        self.fail_once = fail_once
        self._failed = False
        self.calls = calls if calls is not None else []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_once and not self._failed:
            self._failed = True
            raise ValueError("invalid json")
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeClient:
    def __init__(self, content: str = "", fail_once: bool = False, calls: list | None = None):
        self.chat = _FakeChat(_FakeCompletions(content, fail_once=fail_once, calls=calls))


GOOD_JSON = (
    '{"direction":"yes","strength":0.72,'
    '"rationale":"price drift and news lean yes",'
    '"cited_inputs":["current_price","news_summary"]}'
)


def test_signed_strength_bounds():
    yes = NemotronSignal("m", "yes", 0.8, "r", model_id="x")
    no = NemotronSignal("m", "no", 0.5, "r", model_id="x")
    neu = NemotronSignal("m", "neutral", 0.9, "r", model_id="x")
    assert yes.signed_strength == pytest.approx(0.8)
    assert no.signed_strength == pytest.approx(-0.5)
    assert neu.signed_strength == pytest.approx(0.0)


def test_leakage_guard_hard_fails_on_post_close_field():
    with pytest.raises(ValueError, match="leakage gate"):
        assert_pre_close_only(
            {
                "title": "Will X happen?",
                "current_price": 0.4,
                "resolved_at": "2026-01-01T00:00:00Z",
            }
        )


def test_leakage_guard_allows_pre_close_fields():
    assert_pre_close_only(
        {
            "title": "Will X happen?",
            "category": "crypto",
            "current_price": 0.4,
            "past_prices": [0.3, 0.35, 0.4],
            "news_summary": "mildly bullish",
            "news_sentiment": 0.2,
        }
    )


@pytest.mark.asyncio
async def test_flag_off_skips_without_call():
    calls: list = []
    client = _FakeClient(GOOD_JSON, calls=calls)
    result = await fetch_nemotron_signal(
        "m1",
        {"title": "t", "current_price": 0.5},
        settings=_settings(nemotron_signal_enabled=False),
        client=client,
    )
    assert result is None
    assert calls == []


@pytest.mark.asyncio
async def test_missing_nim_key_skips_without_call():
    calls: list = []
    client = _FakeClient(GOOD_JSON, calls=calls)
    result = await fetch_nemotron_signal(
        "m1",
        {"title": "t", "current_price": 0.5},
        settings=_settings(nim_api_key=""),
        client=client,
    )
    assert result is None
    assert calls == []


@pytest.mark.asyncio
async def test_fetch_parses_strict_json_and_caches():
    client = _FakeClient(GOOD_JSON)
    result = await fetch_nemotron_signal(
        "m-cache",
        {"title": "t", "current_price": 0.55, "news_summary": "ok"},
        settings=_settings(),
        client=client,
    )
    assert result is not None
    assert result.direction == "yes"
    assert result.strength == pytest.approx(0.72)
    assert result.model_id == "nvidia/nemotron-3-nano-30b-a3b"
    assert result.prompt_version == "v1"
    assert "prob" not in result.as_provenance()
    # Second call hits cache — no extra create calls beyond first
    n_calls = len(client.chat.completions.calls)
    again = await fetch_nemotron_signal(
        "m-cache",
        {"title": "t", "current_price": 0.55},
        settings=_settings(),
        client=client,
    )
    assert again is result or (again is not None and again.direction == "yes")
    assert len(client.chat.completions.calls) == n_calls


@pytest.mark.asyncio
async def test_rejects_probability_field_from_llm_then_retries():
    # First response illegal (has prob); second is valid — fail_once swaps to good content
    # after first create error path. Here we simulate invalid then valid via custom client.
    class _RetryClient:
        def __init__(self):
            self.n = 0
            self.chat = self

        @property
        def completions(self):
            return self

        async def create(self, **kwargs):
            self.n += 1
            if self.n == 1:
                return _FakeResponse(
                    '{"direction":"yes","strength":0.5,"prob":0.66,"rationale":"x","cited_inputs":[]}'
                )
            return _FakeResponse(GOOD_JSON)

    result = await fetch_nemotron_signal(
        "m-retry",
        {"title": "t", "current_price": 0.5},
        settings=_settings(),
        client=_RetryClient(),
    )
    assert result is not None
    assert result.direction == "yes"
    assert result.strength == pytest.approx(0.72)


@pytest.mark.asyncio
async def test_fetch_raises_on_leaky_context_even_when_flag_off():
    with pytest.raises(ValueError, match="leakage gate"):
        await fetch_nemotron_signal(
            "m-leak",
            {"title": "t", "actual_outcome": 1},
            settings=_settings(nemotron_signal_enabled=False),
            client=_FakeClient(GOOD_JSON),
        )


def test_nemotron_node_off_when_flag_disabled(monkeypatch):
    cache_signal(
        NemotronSignal(
            market_key="nba-2025-01-15-lal-bos",
            direction="yes",
            strength=0.9,
            rationale="cached",
            model_id="nvidia/nemotron-3-nano-30b-a3b",
            prompt_version="v1",
        )
    )
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: _settings(nemotron_signal_enabled=False),
    )
    from app.agents.graph import AgentState

    state = AgentState(market_slug="nba-2025-01-15-lal-bos", features={"implied_yes": 0.55})
    out = nemotron_node(state)
    assert "nemotron_signed_strength" not in out.features


def test_nemotron_node_injects_bounded_feature_and_provenance(monkeypatch):
    cache_signal(
        NemotronSignal(
            market_key="nba-2025-01-15-lal-bos",
            direction="no",
            strength=0.6,
            rationale="injury news",
            cited_inputs=["news_summary"],
            model_id="nvidia/nemotron-3-nano-30b-a3b",
            prompt_version="v1",
        )
    )
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: _settings(nemotron_signal_enabled=True),
    )
    from app.agents.graph import AgentState

    state = AgentState(market_slug="nba-2025-01-15-lal-bos", features={"implied_yes": 0.55})
    out = nemotron_node(state)
    assert out.features["nemotron_signed_strength"] == pytest.approx(-0.6)
    assert -1.0 <= out.features["nemotron_signed_strength"] <= 1.0
    assert out.features["nemotron_model_id"] == "nvidia/nemotron-3-nano-30b-a3b"
    assert out.features["nemotron_prompt_version"] == "v1"
    payload = out.features["nemotron_signal_payload"]
    assert payload["direction"] == "no"
    assert "prob" not in payload
    # Node must not set forecast probability
    assert "predicted_prob" not in out.features or out.predicted_prob == 0.5


def test_graph_includes_nemotron_node():
    names = [n for n, _ in GRAPH_NODES]
    assert "nemotron" in names
    assert names.index("news") < names.index("nemotron") < names.index("memory")
    assert "nemotron" in VETTED_NODE_NAMES


def test_run_agent_graph_with_flag_off_is_noop(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: _settings(nemotron_signal_enabled=False),
    )
    state = run_agent_graph("nba-2025-01-15-lal-bos", {"implied_yes": 0.55})
    assert "nemotron_signed_strength" not in state.features
    assert state.order_intent is not None  # risk path still runs


def test_default_model_id_is_verified_nemotron3_nano():
    from app.core.config import Settings

    s = Settings(NEMOTRON_SIGNAL_ENABLED="false")
    assert s.nemotron_model == "nvidia/nemotron-3-nano-30b-a3b"
    assert s.nemotron_signal_enabled is False


def test_ralph_lab_offline_improves_or_stalls_without_prod_writes(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path

    lab_path = Path(__file__).resolve().parents[1] / "scripts" / "ralph_signal_lab.py"
    spec = importlib.util.spec_from_file_location("ralph_signal_lab", lab_path)
    assert spec is not None and spec.loader is not None
    lab = importlib.util.module_from_spec(spec)
    sys.modules["ralph_signal_lab"] = lab
    spec.loader.exec_module(lab)

    summary = lab.run_ralph_loop(
        tmp_path,
        lab.default_fixture_rows(),
        budget=4,
        k_no_progress=3,
    )
    assert summary["writes_to_prod"] is False
    assert summary["paper_trading_only"] is True
    assert (tmp_path / "PROGRESS.md").is_file()
    assert (tmp_path / "DONE.md").is_file()
    assert summary["iterations"] >= 1
    assert "AutoLab:" in summary["autolab_line"]
    assert summary["baseline_counts"]["n_raw"] == 5
    assert summary["baseline_counts"]["n_effective"] > 0
