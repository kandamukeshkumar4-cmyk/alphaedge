"""U05 — Assistant chat tests.

Covers:
1. Guardrail: ASSISTANT_ALLOWED_TOOLS excludes order tools (submit_order_intent,
   OrderBookService, RiskService paths).
2. Context assembly — returns a dict with expected keys when slug is valid.
3. Deterministic fallback — correct routing for each prompt category.
4. Empty / no-context handling — works with no slug and no LLM key.
5. API endpoint — returns 200 with required fields (paper_trading_only,
   analysis_only_banner).
6. History is honoured (history list accepted without error).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── 1. Guardrail: ASSISTANT_ALLOWED_TOOLS ────────────────────────────────────


def test_assistant_allowed_tools_excludes_order_tools() -> None:
    """submit_order_intent must NOT be in ASSISTANT_ALLOWED_TOOLS."""
    from app.api.v1.assistant import ASSISTANT_ALLOWED_TOOLS

    assert "submit_order_intent" not in ASSISTANT_ALLOWED_TOOLS, (
        "GUARDRAIL VIOLATION: submit_order_intent found in ASSISTANT_ALLOWED_TOOLS"
    )


def test_assistant_allowed_tools_excludes_order_book_service() -> None:
    """The assistant module must NOT import OrderBookService or RiskService."""
    import ast
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "app" / "api" / "v1" / "assistant.py"
    source = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    import_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.names:
                for alias in node.names:
                    import_names.append(alias.name or "")

    assert "OrderBookService" not in import_names, (
        "GUARDRAIL VIOLATION: OrderBookService imported in assistant.py"
    )
    assert "RiskService" not in import_names, (
        "GUARDRAIL VIOLATION: RiskService imported in assistant.py"
    )


def test_assistant_allowed_tools_are_read_only() -> None:
    """Every tool in ASSISTANT_ALLOWED_TOOLS must be a read-only tool name.

    U13 adds get_trader_profile — a read-only profile-derivation tool that
    narrates deterministic stats from paper history.  It is explicitly
    read-only and does not admit any order-execution path.
    """
    from app.api.v1.assistant import ASSISTANT_ALLOWED_TOOLS

    expected_read_only = {
        "get_odds",
        "get_features",
        "get_exposure",
        "get_briefs",
        "get_agent_trace",
        "get_trader_profile",   # U13 — reads paper-history profile, read-only
    }
    assert ASSISTANT_ALLOWED_TOOLS == expected_read_only, (
        f"Tool allowlist mismatch: {ASSISTANT_ALLOWED_TOOLS!r}"
    )


def test_assistant_module_does_not_import_submit_order_intent() -> None:
    """submit_order_intent must never be imported in assistant.py."""
    import ast
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "app" / "api" / "v1" / "assistant.py"
    source = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.append(alias.name or "")

    assert "submit_order_intent" not in imported_names, (
        "GUARDRAIL VIOLATION: submit_order_intent is imported in assistant.py"
    )


# ── 2. Context assembly ───────────────────────────────────────────────────────


def test_gather_market_context_returns_dict_for_unknown_slug() -> None:
    """Should return a dict (possibly empty) — never raise."""
    from app.api.v1.assistant import _gather_market_context

    result = _gather_market_context("unknown-market-slug-xyz")
    assert isinstance(result, dict)
    assert result.get("slug") == "unknown-market-slug-xyz"


def test_gather_market_context_includes_slug() -> None:
    from app.api.v1.assistant import _gather_market_context

    result = _gather_market_context("nba-2025-01-15-lal-bos")
    assert result["slug"] == "nba-2025-01-15-lal-bos"


# ── 3. Deterministic fallback ────────────────────────────────────────────────


def test_deterministic_reply_odds_question() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "Why did odds move today?", {}, "nba-2025-01-15-lal-bos"
    )
    assert isinstance(reply, str) and len(reply) > 0
    assert "get_odds" in tools


def test_deterministic_reply_exposure_question() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "What's my overall exposure?", {}, None
    )
    assert "get_exposure" in tools
    assert "exposure" in reply.lower()
    assert any(c.source == "exposure" for c in citations)


def test_deterministic_reply_bear_case_question() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "What's the bear case?", {}, None
    )
    assert "get_features" in tools
    assert "bear" in reply.lower()


def test_deterministic_reply_briefs_question() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "Show me analyst briefs.", {}, None
    )
    assert "get_briefs" in tools
    assert any(c.source == "briefs" for c in citations)


def test_deterministic_reply_trace_question() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "Explain the model reasoning trace.", {}, "nba-2025-01-15-lal-bos"
    )
    assert "get_agent_trace" in tools


def test_deterministic_reply_fallback() -> None:
    from app.api.v1.assistant import ANALYSIS_ONLY_BANNER, _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "Hello, how are you?", {}, None
    )
    assert ANALYSIS_ONLY_BANNER in reply


def test_deterministic_reply_with_context_includes_model_prob() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    ctx = {"slug": "x", "model_prob": 0.72, "news_sentiment": 0.3, "news_headline": "Test news"}
    reply, citations, tools = _build_deterministic_reply(
        "Why did odds move?", ctx, "x"
    )
    assert "72" in reply or "0.72" in reply or "model" in reply.lower()
    assert any(c.source == "news" for c in citations)


# ── 4. Empty / no-context handling ───────────────────────────────────────────


def test_deterministic_reply_empty_message_handled() -> None:
    """Even a bare fallback should produce a non-empty reply."""
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply("  ", {}, None)
    assert isinstance(reply, str) and len(reply.strip()) > 0


def test_deterministic_reply_no_slug_no_crash() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "Why did odds move?", {}, None
    )
    assert isinstance(reply, str)
    assert "get_odds" in tools


# ── 5. API endpoint ───────────────────────────────────────────────────────────


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_assistant_chat_endpoint_200(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Why did odds move today?", "market_slug": "nba-2025-01-15-lal-bos"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_trading_only"] is True
    assert "analysis only" in data["analysis_only_banner"].lower()
    assert isinstance(data["reply"], str) and len(data["reply"]) > 0


def test_assistant_chat_endpoint_no_slug(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What's my overall exposure?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_trading_only"] is True


def test_assistant_chat_endpoint_tools_used_read_only(client: TestClient) -> None:
    """tools_used in the response must all be in ASSISTANT_ALLOWED_TOOLS."""
    from app.api.v1.assistant import ASSISTANT_ALLOWED_TOOLS

    resp = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Why did odds move today?", "market_slug": "nba-2025-01-15-lal-bos"},
    )
    assert resp.status_code == 200
    tools_used = resp.json().get("tools_used", [])
    for t in tools_used:
        assert t in ASSISTANT_ALLOWED_TOOLS, (
            f"Response tool '{t}' is NOT in ASSISTANT_ALLOWED_TOOLS"
        )


def test_assistant_chat_endpoint_missing_message(client: TestClient) -> None:
    resp = client.post("/api/v1/assistant/chat", json={})
    assert resp.status_code == 422


def test_assistant_chat_endpoint_analysis_banner_always_present(client: TestClient) -> None:
    from app.api.v1.assistant import ANALYSIS_ONLY_BANNER

    resp = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Tell me a joke."},
    )
    assert resp.status_code == 200
    assert resp.json()["analysis_only_banner"] == ANALYSIS_ONLY_BANNER


# ── 6. History handling ───────────────────────────────────────────────────────


def test_assistant_chat_with_history(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Follow-up: what about exposure?",
            "market_slug": "nba-2025-01-15-lal-bos",
            "history": [
                {"role": "user", "content": "Why did odds move?"},
                {"role": "assistant", "content": "Odds moved due to whale activity."},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["paper_trading_only"] is True


# ── 7. LLM gate honours the configured provider (NIM regression) ─────────────


@pytest.mark.asyncio
async def test_llm_reply_uses_llm_when_nim_key_configured(monkeypatch) -> None:
    """With LLM_PROVIDER=nim + NIM_API_KEY set, _llm_reply must call the LLM —
    it previously checked only LLM_API_KEY and silently fell back to the
    deterministic reply, which made deployed NIM configs look 'not analyzing'."""
    import app.api.v1.assistant as assistant_mod
    import app.llm.provider as provider_mod
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        PAPER_TRADING_ONLY=True,
        LLM_PROVIDER="nim",
        NIM_API_KEY="test-nim-key",
    )
    monkeypatch.setattr(assistant_mod, "get_settings", lambda: settings)

    class _FakeCompletions:
        async def create(self, **kwargs):
            class _Msg:
                content = "NIM analysis: odds moved on volume."

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(
        provider_mod, "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_FakeClient(), "test-model"),
    )

    reply, _citations, _tools = await assistant_mod._llm_reply(
        "Why did odds move?", {}, [], None
    )
    assert "NIM analysis" in reply, (
        "assistant took the deterministic-fallback shortcut despite a configured "
        "NIM key — the provider-aware gate regressed"
    )


@pytest.mark.asyncio
async def test_llm_reply_falls_back_without_any_key(monkeypatch) -> None:
    import app.api.v1.assistant as assistant_mod
    from app.core.config import Settings

    settings = Settings(_env_file=None, PAPER_TRADING_ONLY=True)
    monkeypatch.setattr(assistant_mod, "get_settings", lambda: settings)

    reply, _citations, tools = await assistant_mod._llm_reply(
        "Why did odds move?", {}, [], None
    )
    assert reply
    assert tools, "deterministic fallback should report the tools it used"
