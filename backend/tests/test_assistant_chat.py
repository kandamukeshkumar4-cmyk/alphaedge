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
    assert "**Drivers:**" in reply or "Drivers:" in reply
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


@pytest.mark.asyncio
async def test_analyze_prediction_prefers_stored_prediction(monkeypatch) -> None:
    """M1: a persisted forecast wins; the pipeline is not invoked."""
    from types import SimpleNamespace

    import app.api.v1.assistant as assistant_mod

    class StoredPredictionDb:
        async def scalar(self, statement):
            return SimpleNamespace(predicted_prob=0.6123, confidence=0.8)

    async def unexpected_pipeline(*args, **kwargs):
        raise AssertionError("stored prediction must avoid pipeline work")

    monkeypatch.setattr(assistant_mod.asyncio, "to_thread", unexpected_pipeline)
    result = await assistant_mod._prediction_context_for_analyze(
        "nba-2025-01-15-lal-bos", StoredPredictionDb()
    )
    assert result == {
        "model_prob": 0.6123,
        "confidence": 0.8,
        "forecast_reason": "latest stored prediction",
        "prediction_source": "stored",
    }


@pytest.mark.asyncio
async def test_analyze_prediction_pipeline_is_cached_for_sixty_seconds(monkeypatch) -> None:
    """M1: repeated no-log Analyze requests reuse the in-process cache."""
    from types import SimpleNamespace

    import app.api.v1.assistant as assistant_mod
    from app.core import leaderboard_cache

    class NoStoredPredictionDb:
        async def scalar(self, statement):
            return None

    calls = 0

    async def fake_pipeline(func, features):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            predicted_prob=0.58,
            confidence=0.64,
            is_edge=False,
            reason="closing-line edge gate not met",
        )

    leaderboard_cache.invalidate()
    monkeypatch.setattr(assistant_mod.asyncio, "to_thread", fake_pipeline)
    try:
        first = await assistant_mod._prediction_context_for_analyze(
            "nba-2025-01-15-lal-bos", NoStoredPredictionDb()
        )
        second = await assistant_mod._prediction_context_for_analyze(
            "nba-2025-01-15-lal-bos", NoStoredPredictionDb()
        )
    finally:
        leaderboard_cache.invalidate()
    assert calls == 1
    assert first == second
    assert first["prediction_source"] == "on-demand"


@pytest.mark.asyncio
async def test_analyze_prediction_unscorable_clause_is_honest() -> None:
    """M1: a market outside the existing pipeline is named, not assigned a number."""
    import app.api.v1.assistant as assistant_mod

    class NoStoredPredictionDb:
        async def scalar(self, statement):
            return None

    context = await assistant_mod._prediction_context_for_analyze(
        "not-in-the-prediction-catalog", NoStoredPredictionDb()
    )
    reply, _citations, _tools = assistant_mod._build_analyze_reply(
        {"slug": "not-in-the-prediction-catalog", **context},
        "not-in-the-prediction-catalog",
    )
    assert "outside the prediction catalog" in reply
    assert "50.0%" not in reply


def test_bear_case_depth_uses_real_context_only() -> None:
    """M2: source-backed adverse move, liquidity, and close facts are narrated."""
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "What is the bear case?",
        {
            "title": "Lakers vs Celtics",
            "volume": 2_000_000,
            "move_24h": -0.035,
            "volume_percentile": 12.5,
            "hours_to_close": 18.0,
            "negative_drivers": [
                {"label": "Price Jump", "note": "Price Jump signal, -3.5¢"}
            ],
        },
        "nba-2025-01-15-lal-bos",
    )
    assert "Top negative drivers" in reply
    assert "-3.5%" in reply
    assert "percentile 12" in reply
    assert "18.0 hours" in reply
    assert "get_features" in tools
    assert any(citation.source == "odds" for citation in citations)


def test_bear_case_depth_omits_missing_data() -> None:
    """M2: missing stores remain explicit omissions rather than generic claims."""
    from app.api.v1.assistant import _build_deterministic_reply

    reply, _citations, _tools = _build_deterministic_reply(
        "What is the bear case?", {}, "nba-2025-01-15-lal-bos"
    )
    assert "omitted" in reply.lower()
    assert "whale selling pressure" not in reply.lower()


def test_authenticated_market_exposure_is_descriptive_math() -> None:
    """M3: position, concentration, and adverse-resolution amount are exact math."""
    from app.api.v1.assistant import _build_deterministic_reply

    reply, citations, tools = _build_deterministic_reply(
        "What is my exposure in this market?",
        {
            "exposure_authenticated": True,
            "market_positions": [
                {"outcome": "YES", "shares": 10, "avg_cost": 0.6, "cost": 6.0}
            ],
            "market_concentration_pct": 30.0,
        },
        "nba-2025-01-15-lal-bos",
    )
    assert "10 shares" in reply
    assert "−$6.00" in reply
    assert "30.0%" in reply
    assert "should" not in reply.lower()
    assert tools == ["get_exposure"]
    assert citations[0].source == "exposure"


def test_exposure_beats_bear_case_when_resolution_is_against_position() -> None:
    """M3: the natural adverse-resolution prompt must not be routed to M2."""
    from app.api.v1.assistant import _build_deterministic_reply

    reply, _citations, tools = _build_deterministic_reply(
        "What would a resolution against my position do to my balance?",
        {
            "exposure_authenticated": True,
            "market_positions": [
                {"outcome": "YES", "shares": 10, "avg_cost": 0.6, "cost": 6.0}
            ],
            "market_concentration_pct": 30.0,
        },
        "nba-2025-01-15-lal-bos",
    )
    assert tools == ["get_exposure"]
    assert "−$6.00" in reply
    assert "Bear-case data" not in reply


def test_anonymous_market_exposure_is_honest_about_missing_user_data() -> None:
    """M3: unauthenticated users never receive a fabricated portfolio position."""
    from app.api.v1.assistant import _build_deterministic_reply

    reply, _citations, tools = _build_deterministic_reply(
        "What is my exposure in this market?", {}, "nba-2025-01-15-lal-bos"
    )
    assert "Sign in" in reply
    assert "position and portfolio concentration" in reply
    assert tools == ["get_exposure"]


def test_analyze_drivers_are_humanized_deduped_with_magnitude(monkeypatch) -> None:
    """Signal drivers: humanized labels, dedupe by signal type with net direction/
    magnitude — never raw 'delta:price_jump' repeats or duplicate labels."""
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

    async def fake_decision_blocks(slug, out, db):
        return None

    monkeypatch.setattr(alerts_feed, "_build_alert_feed", fake_feed)
    monkeypatch.setattr(
        "app.api.v1.assistant._enrich_analyze_decision_blocks",
        fake_decision_blocks,
    )

    out = asyncio.run(
        _enrich_analyze_context("nba-2025-01-15-lal-bos", {}, MagicMock())
    )
    drivers = out.get("drivers") or []
    assert len(drivers) == 1, drivers
    d = drivers[0]
    assert d["label"] == "Price Jump"
    assert d["direction"] == "favors YES"
    assert "Price Jump signal" in d["note"]
    assert "3 events" in d["note"]
    assert "+12¢" in d["note"] or "net +" in d["note"]
    assert "delta:price_jump" not in (d["label"] + d["note"])
    # Same label must never appear twice
    labels = [x["label"] for x in drivers]
    assert len(labels) == len(set(labels))


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

    async def fake_decision_blocks(slug, out, db):
        return None

    monkeypatch.setattr(alerts_feed, "_build_alert_feed", fake_feed)
    monkeypatch.setattr(
        "app.api.v1.assistant._enrich_analyze_decision_blocks",
        fake_decision_blocks,
    )

    out = asyncio.run(
        _enrich_analyze_context("nba-2025-01-15-lal-bos", {}, MagicMock())
    )
    drivers = out.get("drivers") or []
    assert len(drivers) == 1
    d = drivers[0]
    assert d["label"] == "Momentum"
    assert "Momentum signal" in d["note"]
    assert d["direction"] == "neutral"


def test_what_would_change_uses_real_lean_threshold() -> None:
    """Flip conditions cite the 2pp lean threshold already used by _lean_label."""
    from app.api.v1.assistant import _what_would_change_conditions

    conditions = _what_would_change_conditions(
        {"model_prob": 0.58, "market_price": 0.54, "whale_pressure": 0.4}
    )
    assert len(conditions) == 2
    assert any("2pp" in c for c in conditions)
    assert any("whale" in c for c in conditions)
    # Never advice language
    joined = " ".join(conditions).lower()
    assert "recommend" not in joined
    assert "should" not in joined
    assert "bet" not in joined


def test_build_analyze_reply_sections_omit_absent_fields() -> None:
    """A3 reply uses section labels; absent blocks are omitted (no N/A noise)."""
    from app.api.v1.assistant import (
        ANALYSIS_ONLY_BANNER,
        PAPER_ONLY_DISCLAIMER,
        _build_analyze_reply,
    )

    reply, _citations, _tools = _build_analyze_reply(
        {
            "title": "Lakers vs Celtics",
            "model_prob": 0.58,
            "market_price": 0.54,
            "edge": 0.04,
            "volume": 1000,
            "move_24h": 0.02,
            "price_24h_ago": 0.52,
            "price_7d_low": 0.48,
            "price_7d_high": 0.56,
            "volume_percentile": 72.0,
            "whale_pressure": 0.3,
            "venue_gap": 0.015,
            "news_tone": 0.2,
            "hours_to_close": 12.5,
            "locked_forecast": False,
            "what_would_change": [
                "model–market gap shrinking below 2pp (now 4.0%)",
            ],
            "drivers": [
                {
                    "label": "Price Jump",
                    "direction": "favors YES",
                    "note": "Price Jump signal, 3 events, net +12¢",
                }
            ],
        },
        "nba-2025-01-15-lal-bos",
    )
    assert "**Price:**" in reply
    assert "**Model:**" in reply
    assert "**Drivers:**" in reply
    assert "**Market context:**" in reply
    assert "whale pressure" in reply
    assert "**Time:**" in reply
    assert "no locked forecast yet" in reply
    assert "**What would change this:**" in reply
    assert "7d range" in reply
    assert "N/A" not in reply
    assert ANALYSIS_ONLY_BANNER in reply
    assert PAPER_ONLY_DISCLAIMER in reply
    assert "recommend" not in reply.lower()
    assert "bet size" not in reply.lower()



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
