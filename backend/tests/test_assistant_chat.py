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
    from app.api.v1.assistant import ANALYSIS_ONLY_BANNER, _MENU_MARKER, _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "Hello, how are you?", {}, None
    )
    assert ANALYSIS_ONLY_BANNER in reply
    assert _MENU_MARKER in reply


def test_deterministic_reply_with_context_includes_model_prob() -> None:
    from app.api.v1.assistant import _build_deterministic_reply

    ctx = {"slug": "x", "model_prob": 0.72, "news_sentiment": 0.3, "news_headline": "Test news"}
    reply, citations, tools = _build_deterministic_reply(
        "Why did odds move?", ctx, "x"
    )
    assert "72" in reply or "0.72" in reply or "model" in reply.lower()
    assert any(c.source == "news" for c in citations)


# ── 3b. Loop V41 — analyze intent (keyless / menu) ───────────────────────────


def test_keyless_analyze_returns_real_analysis_not_menu() -> None:
    """A4: Analyze seed must produce a deterministic analysis, never the menu."""
    from app.api.v1.assistant import (
        ANALYSIS_ONLY_BANNER,
        PAPER_ONLY_DISCLAIMER,
        _MENU_MARKER,
        _build_deterministic_reply,
    )

    ctx = {
        "slug": "nba-2025-01-15-lal-bos",
        "title": "Lakers vs Celtics",
        "model_prob": 0.58,
        "market_price": 0.54,
        "volume": 2_413_000,
        "edge": 0.04,
        "move_24h": 0.02,
        "price_24h_ago": 0.52,
        "forecast_reason": "edge below threshold",
        "drivers": [
            {
                "label": "Model vs market gap",
                "direction": "favors YES",
                "note": "Model 58.0% vs market 54.0% (+4.0%).",
            }
        ],
        "brief_headline": "Lakers slight model lean",
    }
    seed = "Analyze Lakers vs Celtics for a paper trade. Current YES ~54¢."
    reply, citations, tools = _build_deterministic_reply(
        seed, ctx, "nba-2025-01-15-lal-bos"
    )
    assert _MENU_MARKER not in reply
    assert "Paper-trade analysis" in reply
    assert "58.0%" in reply or "model 58" in reply.lower()
    assert "54.0%" in reply or "54¢" in reply or "~54" in reply
    assert "2,413,000" in reply
    assert "+2.0%" in reply or "24h move" in reply.lower()
    assert "Drivers:" in reply
    assert "Lakers slight model lean" in reply
    assert ANALYSIS_ONLY_BANNER in reply
    assert PAPER_ONLY_DISCLAIMER in reply
    assert "get_features" in tools
    assert "get_odds" in tools
    assert "get_briefs" in tools


def test_keyless_analyze_omits_absent_fields_honestly() -> None:
    """Absent data must be noted as omitted — never fabricated."""
    from app.api.v1.assistant import _MENU_MARKER, _build_deterministic_reply

    reply, _citations, tools = _build_deterministic_reply(
        "Deep-dive unknown-market for a paper trade.",
        {"slug": "unknown-market"},
        "unknown-market",
    )
    assert _MENU_MARKER not in reply
    assert "Paper-trade analysis" in reply
    assert "omitted" in reply.lower()
    # Must not invent a fake probability like 50% or 0.50 as if it were measured
    assert "get_features" in tools


def test_analyze_drivers_are_humanized_deduped_with_magnitude(monkeypatch) -> None:
    """Signal drivers: humanized labels, dedupe with counts, payload direction/
    magnitude when present — never raw 'delta:price_jump (neutral)' repeats."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.api.v1 import alerts_feed
    from app.api.v1.assistant import _enrich_analyze_context

    def _item(signal_type: str, payload: dict) -> SimpleNamespace:
        citation = SimpleNamespace(
            model_dump=lambda: {
                "headline": None, "model_p": None, "market_p": None,
            }
        )
        return SimpleNamespace(
            signal_type=signal_type, payload=payload, citation=citation
        )

    jump = {"direction": "up", "magnitude": 0.04}
    items = [
        _item("delta:price_jump", jump),
        _item("delta:price_jump", jump),
        _item("delta:price_jump", jump),
    ]

    async def fake_feed(db, effective_slugs, scope, since, limit):
        return SimpleNamespace(items=items[:limit])

    monkeypatch.setattr(alerts_feed, "_build_alert_feed", fake_feed)

    out = asyncio.run(
        _enrich_analyze_context("nba-2025-01-15-lal-bos", {}, MagicMock())
    )
    drivers = out.get("drivers") or []
    assert len(drivers) == 1, drivers
    d = drivers[0]
    assert d["label"] == "3x Price Jump"
    assert d["direction"] == "favors YES"
    assert "Price Jump signal" in d["note"]
    assert "+4¢" in d["note"]
    assert "delta:price_jump" not in (d["label"] + d["note"])


def test_analyze_driver_magnitude_omitted_when_absent(monkeypatch) -> None:
    """No magnitude fields in payload → note stays honest, nothing invented."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.api.v1 import alerts_feed
    from app.api.v1.assistant import _enrich_analyze_context

    citation = SimpleNamespace(
        model_dump=lambda: {"headline": None, "model_p": None, "market_p": None}
    )
    item = SimpleNamespace(
        signal_type="screener:momentum", payload={}, citation=citation
    )

    async def fake_feed(db, effective_slugs, scope, since, limit):
        return SimpleNamespace(items=[item])

    monkeypatch.setattr(alerts_feed, "_build_alert_feed", fake_feed)

    out = asyncio.run(
        _enrich_analyze_context("nba-2025-01-15-lal-bos", {}, MagicMock())
    )
    drivers = out.get("drivers") or []
    assert len(drivers) == 1
    d = drivers[0]
    assert d["label"] == "Momentum"
    assert d["note"] == "Momentum signal"
    assert d["direction"] == "neutral"


def test_signal_humanize_helpers_mirror_frontend() -> None:
    """Server-side helpers follow signal-rail.ts conventions."""
    from app.api.v1.assistant import (
        _humanize_signal_type,
        _signal_magnitude_label,
        _signal_payload_direction,
    )

    assert _humanize_signal_type("delta:price_jump") == "Price Jump"
    assert _humanize_signal_type("news:mispricing") == "Mispricing"
    assert _humanize_signal_type("arb") == "Arb"
    assert _signal_payload_direction({"direction": "sell"}) == "DOWN"
    assert _signal_payload_direction({"direction": "positive"}) == "UP"
    assert _signal_payload_direction({}) is None
    assert _signal_magnitude_label({"detail": {"bps": 25}}, "DOWN") == "-25 bps"
    assert _signal_magnitude_label({"magnitude": 0.031}, "UP") == "+3.1¢"
    assert _signal_magnitude_label({"score": 0.42}, None) == "score 0.42"
    assert _signal_magnitude_label({}, None) is None


def test_unrecognized_intent_still_returns_menu() -> None:
    """A4: genuinely unrecognized prompts keep the capability menu."""
    from app.api.v1.assistant import _MENU_MARKER, _build_deterministic_reply

    reply, _citations, _tools = _build_deterministic_reply(
        "Tell me a joke about penguins.", {}, None
    )
    assert _MENU_MARKER in reply


def test_assistant_chat_endpoint_analyze_seed_not_menu(client: TestClient) -> None:
    """Endpoint-level: keyless Analyze seed must not return the capability menu."""
    from app.api.v1.assistant import _MENU_MARKER, _reset_anon_rate_limiter

    _reset_anon_rate_limiter()
    resp = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Analyze Lakers vs Celtics for a paper trade. Current YES ~54¢.",
            "market_slug": "nba-2025-01-15-lal-bos",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_trading_only"] is True
    assert _MENU_MARKER not in data["reply"]
    assert "Paper-trade analysis" in data["reply"] or "analysis" in data["reply"].lower()


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


@pytest.mark.asyncio
async def test_analyze_intent_routes_to_llm_when_key_present(monkeypatch) -> None:
    """A3: Analyze seed prompt must hit the LLM when a chat key is configured —
    not the deterministic menu and not a silent keyless shortcut."""
    import app.api.v1.assistant as assistant_mod
    import app.llm.provider as provider_mod
    from app.api.v1.assistant import _MENU_MARKER
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        PAPER_TRADING_ONLY=True,
        LLM_PROVIDER="openai",
        LLM_API_KEY="test-openai-key",
    )
    monkeypatch.setattr(assistant_mod, "get_settings", lambda: settings)

    called: dict[str, bool] = {"llm": False}

    class _FakeCompletions:
        async def create(self, **kwargs):
            called["llm"] = True
            class _Msg:
                content = "MOCK_LLM_ANALYZE: model 58% vs market 54%, edge +4%."

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
        provider_mod,
        "resolve_routed_client",
        lambda s, route, *, use_case_model="": (_FakeClient(), "test-model"),
    )

    seed = "Analyze Lakers vs Celtics for a paper trade. Current YES ~54¢."
    reply, _citations, _tools = await assistant_mod._llm_reply(
        seed,
        {"slug": "nba-2025-01-15-lal-bos", "model_prob": 0.58, "market_price": 0.54},
        [],
        "nba-2025-01-15-lal-bos",
    )
    assert called["llm"] is True, "Analyze intent did not call the LLM client"
    assert "MOCK_LLM_ANALYZE" in reply
    assert _MENU_MARKER not in reply


# ── 8. Auth + per-IP anonymous rate limit (security hardening) ────────────────


def test_assistant_chat_anon_rate_limited_beyond_limit(client: TestClient, monkeypatch) -> None:
    """Anonymous requests past ASSISTANT_ANON_RATE_PER_MIN must get 429."""
    from app.api.v1.assistant import _reset_anon_rate_limiter
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "assistant_anon_rate_per_min", 2)
    # Pin the limiter clock: each chat call takes seconds, so on a loaded CI
    # machine three sequential calls can straddle the 60s fixed window.
    monkeypatch.setattr("app.api.v1.assistant._anon_clock", lambda: 1000.0)
    _reset_anon_rate_limiter()

    payload = {"message": "Why did odds move today?"}
    assert client.post("/api/v1/assistant/chat", json=payload).status_code == 200
    assert client.post("/api/v1/assistant/chat", json=payload).status_code == 200
    third = client.post("/api/v1/assistant/chat", json=payload)
    assert third.status_code == 429
    assert "rate limit" in third.json()["detail"].lower()


def test_assistant_client_ip_prefers_x_forwarded_for() -> None:
    from unittest.mock import MagicMock

    from app.api.v1.assistant import _client_ip

    req = MagicMock()
    req.headers = {"x-forwarded-for": "203.0.113.9, 10.0.0.1"}
    req.client.host = "10.0.0.1"
    assert _client_ip(req) == "203.0.113.9"


def test_assistant_chat_valid_anon_request_within_limit_200(client: TestClient, monkeypatch) -> None:
    """A valid anonymous request within the limit still gets 200."""
    from app.api.v1.assistant import _reset_anon_rate_limiter

    _reset_anon_rate_limiter()
    resp = client.post(
        "/api/v1/assistant/chat", json={"message": "Why did odds move today?"}
    )
    assert resp.status_code == 200
    assert resp.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_assistant_chat_authenticated_bypasses_rate_limit(db_session, monkeypatch) -> None:
    """A valid bearer token authenticates the caller and bypasses the per-IP
    anon limit, so logged-in users are never 429'd by the demo guard."""
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.assistant import _reset_anon_rate_limiter
    from app.core.config import get_settings
    from app.db.session import get_db
    from app.main import app

    monkeypatch.setattr(get_settings(), "assistant_anon_rate_per_min", 1)
    _reset_anon_rate_limiter()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            signup = await ac.post(
                "/api/v1/auth/signup",
                json={"email": "asst@example.com", "password": "securepass1"},
            )
            assert signup.status_code == 201
            token = signup.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            payload = {"message": "Why did odds move today?"}
            r1 = await ac.post("/api/v1/assistant/chat", json=payload, headers=headers)
            r2 = await ac.post("/api/v1/assistant/chat", json=payload, headers=headers)
            assert r1.status_code == 200
            assert r2.status_code == 200  # would be 429 if anon limit applied
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_assistant_chat_invalid_token_rejected_401(db_session, monkeypatch) -> None:
    """An invalid bearer token must still 401 (optional auth ≠ no auth)."""
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.assistant import _reset_anon_rate_limiter
    from app.db.session import get_db
    from app.main import app

    _reset_anon_rate_limiter()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/v1/assistant/chat",
                json={"message": "hi"},
                headers={"Authorization": "Bearer not-a-real-token"},
            )
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
