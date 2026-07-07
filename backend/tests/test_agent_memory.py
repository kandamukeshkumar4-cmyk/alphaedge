"""loop3 — agent memory store, resolution learning loop, memory graph node."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.models import AgentMemory
from app.db.session import get_db
from app.main import app
from app.services.memory_service import find_similar, store_resolution, summarize_memories


def _market(slug="pm-lal-bos-2026", question="Will the Lakers beat the Celtics?", category="Sports"):
    return SimpleNamespace(slug=slug, question=question, category=category)


def _forecast(user_prob=0.7, implied=0.55):
    return SimpleNamespace(user_probability=user_prob, market_implied_probability=implied)


# ── TASK 1: memory store ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_and_retrieve_by_category_fallback(db_session):
    await store_resolution(
        db_session,
        _market(slug="pm-lal-bos", question="Will the Lakers beat the Celtics tonight?"),
        _forecast(0.7, 0.55),
        outcome=1,
    )
    await store_resolution(
        db_session,
        _market(slug="pm-gsw", question="Will the Warriors win the championship?"),
        _forecast(0.4, 0.5),
        outcome=0,
    )
    # A politics memory in a different category must not surface for Sports.
    await store_resolution(
        db_session,
        _market(slug="pm-elec", question="Will the incumbent win the election?", category="Politics"),
        _forecast(0.6, 0.5),
        outcome=1,
    )

    results = await find_similar(db_session, "Lakers Celtics game tonight", "Sports", k=5)
    assert len(results) == 2  # only same-category rows
    assert all(m.category == "Sports" for m in results)
    # Keyword overlap ranks the Lakers/Celtics memory first.
    assert results[0].market_slug == "pm-lal-bos"


@pytest.mark.asyncio
async def test_store_computes_outcome_and_brier(db_session):
    mem = await store_resolution(db_session, _market(), _forecast(0.7, 0.55), outcome=1)
    assert mem is not None
    assert mem.outcome == "YES"
    assert mem.model_prob_at_close == pytest.approx(0.7)
    assert mem.market_prob_at_close == pytest.approx(0.55)
    # brier = (0.7 - 1)^2
    assert mem.brier == pytest.approx(0.09, abs=1e-6)
    assert mem.embedding is None  # no provider configured in tests


@pytest.mark.asyncio
async def test_find_similar_returns_at_most_k(db_session):
    for i in range(6):
        await store_resolution(
            db_session,
            _market(slug=f"pm-{i}", question=f"Will team {i} win the game?"),
            _forecast(0.5, 0.5),
            outcome=i % 2,
        )
    results = await find_similar(db_session, "Will a team win the game?", "Sports", k=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_find_similar_k_zero_returns_empty(db_session):
    await store_resolution(db_session, _market(), _forecast(), outcome=1)
    assert await find_similar(db_session, "anything", "Sports", k=0) == []


@pytest.mark.asyncio
async def test_embedding_failure_still_stores(db_session):
    def _boom(_text):
        raise RuntimeError("embedding provider exploded")

    mem = await store_resolution(
        db_session, _market(), _forecast(0.8, 0.6), outcome=1, embed_fn=_boom
    )
    assert mem is not None
    assert mem.embedding is None
    count = await db_session.scalar(select(func.count()).select_from(AgentMemory))
    assert count == 1


# ── TASK 2: write path hooks resolution ──────────────────────────────────────


@pytest.mark.asyncio
async def test_scoring_a_forecast_creates_one_memory_row(db_session):
    from app.db.models import ExternalMarketStatus, Platform
    from app.forecasting.market_source import ManualAdapter, get_adapter, register_adapter
    from app.services.external_market_service import ExternalMarketService
    from app.services.forecast_service import ForecastService
    from app.services.forecaster_service import ForecasterService
    from app.services.scoring_service import ScoringService

    prev = get_adapter(Platform.POLYMARKET)
    register_adapter(Platform.POLYMARKET, ManualAdapter())
    try:
        forecaster, _t, _c = await ForecasterService(db_session).create_anonymous()
        market = await ExternalMarketService(db_session).resolve_url(
            "https://polymarket.com/event/will-it-rain-2026"
        )
        await ForecastService(db_session).lock_forecast(forecaster, market, 0.7, 0.5)

        # Resolve the market strictly after the forecast lock, then score.
        market.status = ExternalMarketStatus.RESOLVED
        market.winning_outcome = 1
        market.resolved_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db_session.flush()

        scored = await ScoringService(db_session).score_market(market)
        assert scored == 1

        rows = (await db_session.execute(select(AgentMemory))).scalars().all()
        assert len(rows) == 1
        assert rows[0].outcome == "YES"
        assert rows[0].brier == pytest.approx((0.7 - 1) ** 2, abs=1e-5)
    finally:
        register_adapter(Platform.POLYMARKET, prev)


# ── TASK 3: read path memory node in the agent graph ─────────────────────────


def test_memory_node_registered_and_vetted():
    from app.agents.clone_service import VETTED_NODE_NAMES, validate_nodes
    from app.agents.graph import GRAPH_NODES

    assert "memory" in dict(GRAPH_NODES)
    assert "memory" in VETTED_NODE_NAMES
    # A clone may select the memory node.
    assert validate_nodes(["data", "memory", "prediction"]) == ["data", "memory", "prediction"]


def test_memory_node_injects_context_from_features():
    from app.agents.graph import AgentState, memory_node, reasoning_node

    cases = [
        {
            "question": "Will the Lakers beat the Celtics?",
            "model_prob_at_close": 0.7,
            "market_prob_at_close": 0.55,
            "outcome": "YES",
            "brier": 0.09,
        }
    ]
    state = AgentState(market_slug="pm-x", features={"memory_similar_cases": cases})
    state = memory_node(state)
    assert "memory_context" in state.features
    assert "similar past markets" in state.features["memory_context"]
    assert state.features["memory_case_count"] == 1

    # Downstream reasoning node surfaces the memory context.
    state = reasoning_node(state)
    assert "Memory:" in state.reasoning


def test_memory_node_calls_provider():
    from app.agents.graph import AgentState, memory_node, set_memory_provider

    calls = {}

    def _provider(question, category, k):
        calls["args"] = (question, category, k)
        return [
            {
                "question": "Past market",
                "model_prob_at_close": 0.6,
                "market_prob_at_close": 0.5,
                "outcome": "NO",
                "brier": 0.36,
            }
        ]

    set_memory_provider(_provider)
    try:
        state = AgentState(
            market_slug="pm-y",
            features={"question": "New question?", "category": "Politics"},
        )
        state = memory_node(state)
    finally:
        set_memory_provider(None)

    assert calls["args"] == ("New question?", "Politics", 3)
    assert "memory_context" in state.features


def test_memory_node_is_context_only():
    """Guardrail: memory must not mutate probabilities or approval."""
    from app.agents.graph import AgentState, memory_node

    state = AgentState(
        market_slug="pm-z",
        predicted_prob=0.42,
        confidence=0.33,
        approved=True,
        features={"memory_similar_cases": [{"question": "q", "outcome": "YES"}]},
    )
    before_prob, before_conf, before_ok = state.predicted_prob, state.confidence, state.approved
    state = memory_node(state)
    assert state.predicted_prob == before_prob
    assert state.confidence == before_conf
    assert state.approved == before_ok
    assert state.order_intent is None


def test_memory_node_no_cases_is_noop():
    from app.agents.graph import AgentState, memory_node, set_memory_provider

    set_memory_provider(None)
    state = AgentState(market_slug="pm-none", features={"question": "q?", "category": "Sports"})
    state = memory_node(state)
    assert "memory_context" not in state.features


def test_summarize_memories_compact_format():
    summary = summarize_memories(
        [
            {
                "question": "Will X happen?",
                "model_prob_at_close": 0.7,
                "market_prob_at_close": 0.55,
                "outcome": "YES",
                "brier": 0.09,
            }
        ]
    )
    assert summary.startswith("similar past markets: [")
    assert "model 70% vs mkt 55% -> YES" in summary
    assert summarize_memories([]) == ""


# ── TASK 4: learning feedback surface ────────────────────────────────────────


@pytest.mark.asyncio
async def test_memories_endpoint_returns_newest_first(db_session):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(3):
        db_session.add(
            AgentMemory(
                market_slug=f"pm-{i}",
                category="Sports",
                question=f"Question {i}?",
                outcome="YES",
                model_prob_at_close=0.6,
                market_prob_at_close=0.5,
                brier=0.16,
                rationale_summary="r",
                created_at=base + timedelta(hours=i),
            )
        )
    # A different category row to test the filter.
    db_session.add(
        AgentMemory(
            market_slug="pm-pol",
            category="Politics",
            question="Election?",
            outcome="NO",
            rationale_summary="r",
            created_at=base + timedelta(hours=5),
        )
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/memories")
            assert resp.status_code == 200
            items = resp.json()["items"]
            # Newest first across all categories.
            slugs = [it["market_slug"] for it in items]
            assert slugs[0] == "pm-pol"
            assert slugs[1] == "pm-2"

            filtered = await client.get("/api/v1/memories?category=Sports&limit=2")
            assert filtered.status_code == 200
            f_items = filtered.json()["items"]
            assert len(f_items) == 2
            assert all(it["category"] == "Sports" for it in f_items)
            assert f_items[0]["market_slug"] == "pm-2"
    finally:
        app.dependency_overrides.clear()
