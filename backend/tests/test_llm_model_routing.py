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
    """End-to-end through write_brief: state.deep=True must send the deep route's
    model id to the chat-completions call."""
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    settings = _settings(
        LLM_MODEL_DEEP="nemotron-49b",
        LLM_API_KEY="k",
        LLM_PROVIDER="openai",
        GLM_API_KEY="glm-test",
        GLM_MODEL="glm-4-plus",
        LLM_ROUTE_ANALYST_DEEP="glm",
    )
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

    monkeypatch.setattr(
        provider_mod, "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_Client(), "glm-4-plus"),
    )

    state = analyst_mod.AnalystState(market_slug="nba-2025-01-15-lal-bos", deep=True)
    state.market_state = {"title": "Lakers vs Celtics", "implied_yes": 0.55}
    state.evidence = {"model": {"predicted_prob": 0.55, "edge": 0.0}}

    result = await analyst_mod.write_brief(state, settings)
    assert captured["model"] == "glm-4-plus"
    assert result.generator == "llm"


async def test_write_brief_uses_fast_model_when_not_deep(monkeypatch):
    import app.agents.analyst as analyst_mod
    import app.llm.provider as provider_mod

    settings = _settings(
        LLM_MODEL_DEEP="nemotron-49b",
        LLM_API_KEY="k",
        LLM_PROVIDER="openai",
        KIMI_API_KEY="kimi-test",
        KIMI_MODEL="moonshot-v1-8k",
        LLM_ROUTE_ANALYST="kimi",
    )
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

    monkeypatch.setattr(
        provider_mod, "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_Client(), "moonshot-v1-8k"),
    )

    state = analyst_mod.AnalystState(market_slug="nba-2025-01-15-lal-bos", deep=False)
    state.market_state = {"title": "Lakers vs Celtics", "implied_yes": 0.55}
    state.evidence = {"model": {"predicted_prob": 0.55, "edge": 0.0}}

    await analyst_mod.write_brief(state, settings)
    assert captured["model"] == "moonshot-v1-8k"


def test_route_fallback_to_primary():
    """When no per-use-case key is set, routing falls back to primary provider."""
    from app.llm.provider import _resolve_route_endpoint

    settings = _settings(LLM_API_KEY="sk-test")
    assert _resolve_route_endpoint(settings, "") is None
    assert _resolve_route_endpoint(settings, "deepseek") is None  # no DEEPSEEK_API_KEY


def test_route_deepseek_resolves():
    from app.llm.provider import _resolve_route_endpoint

    settings = _settings(DEEPSEEK_API_KEY="ds-test", DEEPSEEK_MODEL="deepseek-chat")
    result = _resolve_route_endpoint(settings, "deepseek")
    assert result is not None
    assert result[1] == "ds-test"
    assert result[2] == "deepseek-chat"


def test_route_kimi_resolves():
    from app.llm.provider import _resolve_route_endpoint

    settings = _settings(KIMI_API_KEY="ki-test", KIMI_MODEL="moonshot-v1-8k")
    result = _resolve_route_endpoint(settings, "kimi")
    assert result is not None
    assert result[1] == "ki-test"
    assert result[2] == "moonshot-v1-8k"


def test_route_glm_resolves():
    from app.llm.provider import _resolve_route_endpoint

    settings = _settings(GLM_API_KEY="glm-test", GLM_MODEL="glm-4-flash")
    result = _resolve_route_endpoint(settings, "glm")
    assert result is not None
    assert result[1] == "glm-test"
    assert result[2] == "glm-4-flash"


def test_use_case_model_used_when_route_empty():
    """NIM-native mode: empty route uses per-use-case model, not LLM_MODEL."""
    from app.llm.provider import resolve_routed_client

    settings = _settings(LLM_API_KEY="sk-test")
    _, model = resolve_routed_client(
        settings, "", use_case_model="deepseek-ai/deepseek-r1"
    )
    assert model == "deepseek-ai/deepseek-r1"


def test_use_case_model_falls_back_to_llm_model_when_empty():
    """Empty use_case_model falls back to LLM_MODEL."""
    from app.llm.provider import resolve_routed_client

    settings = _settings(LLM_API_KEY="sk-test")
    _, model = resolve_routed_client(settings, "", use_case_model="")
    assert model == "fast-model"


def test_use_case_model_ignored_when_route_resolves():
    """When a route resolves to a separate provider, use_case_model is ignored."""
    from app.llm.provider import resolve_routed_client

    settings = _settings(
        LLM_API_KEY="sk-test",
        DEEPSEEK_API_KEY="ds-test",
        DEEPSEEK_MODEL="deepseek-chat",
    )
    _, model = resolve_routed_client(
        settings, "deepseek", use_case_model="meta/llama-3.3-70b-instruct"
    )
    assert model == "deepseek-chat"


def test_sync_client_use_case_model():
    """Sync variant also respects use_case_model."""
    from app.llm.provider import resolve_routed_sync_client

    settings = _settings(LLM_API_KEY="sk-test")
    _, model = resolve_routed_sync_client(
        settings, "", use_case_model="deepseek-ai/deepseek-r1"
    )
    assert model == "deepseek-ai/deepseek-r1"
