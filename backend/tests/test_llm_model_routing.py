"""O06: per-feature LLM model routing (deep reasoning model for the digest)."""

from app.core.config import Settings
from app.llm.provider import resolve_llm_model


def _settings(**overrides) -> Settings:
    base = dict(_env_file=None, PAPER_TRADING_ONLY=True, LLM_MODEL="fast-model")
    base.update(overrides)
    return Settings(**base)


def test_resolve_model_defaults_to_llm_model():
    settings = _settings()
    assert resolve_llm_model(settings) == "fast-model"
    assert resolve_llm_model(settings, deep=False) == "fast-model"


def test_deep_falls_back_to_llm_model_when_deep_unset():
    settings = _settings()  # LLM_MODEL_DEEP empty
    assert resolve_llm_model(settings, deep=True) == "fast-model"


def test_deep_uses_llm_model_deep_when_set():
    settings = _settings(LLM_MODEL_DEEP="nemotron-49b")
    assert resolve_llm_model(settings, deep=True) == "nemotron-49b"
    # Non-deep callers must stay on the fast model even when a deep model exists.
    assert resolve_llm_model(settings, deep=False) == "fast-model"


def test_deep_ignores_whitespace_only_deep_model():
    settings = _settings(LLM_MODEL_DEEP="   ")
    assert resolve_llm_model(settings, deep=True) == "fast-model"


async def test_write_brief_sends_deep_model_to_llm(monkeypatch):
    """End-to-end through write_brief: state.deep=True must send LLM_MODEL_DEEP
    as the model id to the chat-completions call."""
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    settings = _settings(LLM_MODEL_DEEP="nemotron-49b", LLM_API_KEY="k", LLM_PROVIDER="openai")
    captured: dict[str, str] = {}

    class _Completions:
        async def create(self, **kwargs):
            captured["model"] = kwargs["model"]

            class _Msg:
                content = "Deep headline\nDeep body."

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Client:
        class chat:  # noqa: N801
            completions = _Completions()

    monkeypatch.setattr(provider_mod, "get_llm_client", lambda s: _Client())

    state = analyst_mod.AnalystState(market_slug="nba-2025-01-15-lal-bos", deep=True)
    state.market_state = {"title": "Lakers vs Celtics", "implied_yes": 0.55}
    state.evidence = {"model": {"predicted_prob": 0.55, "edge": 0.0}}

    result = await analyst_mod.write_brief(state, settings)
    assert captured["model"] == "nemotron-49b"
    assert result.generator == "llm"


async def test_write_brief_uses_fast_model_when_not_deep(monkeypatch):
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    settings = _settings(LLM_MODEL_DEEP="nemotron-49b", LLM_API_KEY="k", LLM_PROVIDER="openai")
    captured: dict[str, str] = {}

    class _Completions:
        async def create(self, **kwargs):
            captured["model"] = kwargs["model"]

            class _R:
                choices = [type("C", (), {"message": type("M", (), {"content": "h\nb"})()})()]

            return _R()

    class _Client:
        class chat:  # noqa: N801
            completions = _Completions()

    monkeypatch.setattr(provider_mod, "get_llm_client", lambda s: _Client())

    state = analyst_mod.AnalystState(market_slug="nba-2025-01-15-lal-bos", deep=False)
    state.market_state = {"title": "Lakers vs Celtics", "implied_yes": 0.55}
    state.evidence = {"model": {"predicted_prob": 0.55, "edge": 0.0}}

    await analyst_mod.write_brief(state, settings)
    assert captured["model"] == "fast-model"
