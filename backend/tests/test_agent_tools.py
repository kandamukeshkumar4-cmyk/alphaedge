"""loop5 — native market-data tool nodes in the agent graph (report §6 MCP capability).

Covers:
  TASK 1 — the three async tools (happy path + failure returns an error dict, never raises).
  TASK 2 — the market_tools graph node, its allowlist membership, reasoning enrichment.
  TASK 3 — the brief schema's tools_used section.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.tools import (
    gather_market_tools,
    get_order_book_summary,
    get_price_history,
    get_whale_activity,
    summarize_tools_used,
)
from app.db.models import (
    Account,
    Market,
    MarketStatus,
    OddsSnapshot,
    Order,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
    WalletPositionSnapshot,
)


class _BrokenSession:
    """A session whose DB calls always raise — proves the tools never propagate."""

    async def scalar(self, *_a, **_k):
        raise RuntimeError("db down")

    async def execute(self, *_a, **_k):
        raise RuntimeError("db down")


class _FakeConnector:
    def fetch_market_snapshot(self, slug):  # noqa: ARG002
        class _Snap:
            implied_yes = 0.62
            metadata = {"yes_bid": 0.60, "executable_yes_ask": 0.64}

        return _Snap()


async def _make_market(session, slug: str = "tool-mkt") -> Market:
    market = Market(
        slug=slug,
        title="Tool Test Market",
        question="Will the tool test pass?",
        status=MarketStatus.OPEN,
    )
    session.add(market)
    await session.flush()
    return market


# ── TASK 1: get_order_book_summary ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_order_book_summary_local_clob_happy_path(db_session):
    market = await _make_market(db_session)
    acct = Account(name="mm", cash_balance=Decimal("100000"))
    db_session.add(acct)
    await db_session.flush()
    # Seed a resting YES book: best bid 0.40, best ask 0.55 -> spread 0.15.
    for side, price in ((OrderSide.BUY, "0.40"), (OrderSide.SELL, "0.55")):
        db_session.add(
            Order(
                market_id=market.id,
                account_id=acct.id,
                side=side,
                outcome=OrderOutcome.YES,
                order_type=OrderType.LIMIT,
                price=Decimal(price),
                quantity=Decimal("25"),
                status=OrderStatus.OPEN,
            )
        )
    await db_session.flush()

    out = await get_order_book_summary(db_session, market.slug)
    assert out["tool"] == "get_order_book_summary"
    assert out["source"] == "local_clob"
    assert out["best_bid"] == 0.40
    assert out["best_ask"] == 0.55
    assert out["spread"] == 0.15
    assert len(out["depth"]["yes"]["bids"]) == 1


@pytest.mark.asyncio
async def test_order_book_summary_unknown_market_returns_error(db_session):
    out = await get_order_book_summary(db_session, "does-not-exist")
    assert out == {"error": "market 'does-not-exist' not found", "tool": "get_order_book_summary"}


@pytest.mark.asyncio
async def test_order_book_summary_uses_connector_for_mirrored_market(db_session):
    out = await get_order_book_summary(
        db_session, "live-only", connector=_FakeConnector()
    )
    assert out["source"] == "connector"
    assert out["best_bid"] == 0.60
    assert out["best_ask"] == 0.64
    assert out["spread"] == 0.04


@pytest.mark.asyncio
async def test_order_book_summary_never_raises_on_db_error():
    out = await get_order_book_summary(_BrokenSession(), "x")
    assert out["tool"] == "get_order_book_summary"
    assert "error" in out


# ── TASK 1: get_price_history ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_price_history_happy_path(db_session):
    now = datetime.now(UTC)
    for i, price in enumerate(("0.50", "0.55", "0.60")):
        db_session.add(
            OddsSnapshot(
                id=uuid4(),
                market_slug="ph-mkt",
                implied_yes=Decimal(price),
                source="polymarket-live",
                captured_at=now - timedelta(hours=2 - i),
                outcome_name="Yes",
            )
        )
    await db_session.flush()

    out = await get_price_history(db_session, "ph-mkt", hours=24)
    assert out["tool"] == "get_price_history"
    assert out["points"] == 3
    assert out["first"] == 0.50
    assert out["last"] == 0.60
    assert out["high"] == 0.60
    assert out["change"] == 0.10


@pytest.mark.asyncio
async def test_price_history_excludes_rows_outside_window(db_session):
    now = datetime.now(UTC)
    db_session.add(
        OddsSnapshot(
            id=uuid4(),
            market_slug="ph-old",
            implied_yes=Decimal("0.5"),
            source="s",
            captured_at=now - timedelta(hours=48),
            outcome_name="Yes",
        )
    )
    await db_session.flush()
    out = await get_price_history(db_session, "ph-old", hours=24)
    assert out["points"] == 0
    assert out["last"] is None


@pytest.mark.asyncio
async def test_price_history_never_raises_on_db_error():
    out = await get_price_history(_BrokenSession(), "x")
    assert out["tool"] == "get_price_history"
    assert "error" in out


# ── TASK 1: get_whale_activity ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_whale_activity_happy_path(db_session):
    now = datetime.now(UTC)
    # Same wallet builds its YES position 200 -> 500 (a >100-share ADD).
    for size, minutes in ((Decimal("200"), 60), (Decimal("500"), 5)):
        db_session.add(
            WalletPositionSnapshot(
                id=uuid4(),
                wallet_address="0xWhaleAAAA",
                market_slug="whale-mkt",
                outcome="YES",
                size=size,
                avg_price=Decimal("0.5"),
                captured_at=now - timedelta(minutes=minutes),
            )
        )
    await db_session.flush()

    out = await get_whale_activity(db_session, "whale-mkt")
    assert out["tool"] == "get_whale_activity"
    assert out["whale_count"] == 1
    assert out["deltas"][0]["action"] == "add"
    assert out["deltas"][0]["size_change"] == 300.0


@pytest.mark.asyncio
async def test_whale_activity_ignores_small_moves(db_session):
    now = datetime.now(UTC)
    for size, minutes in ((Decimal("100"), 60), (Decimal("110"), 5)):
        db_session.add(
            WalletPositionSnapshot(
                id=uuid4(),
                wallet_address="0xSmall",
                market_slug="small-mkt",
                outcome="YES",
                size=size,
                avg_price=Decimal("0.5"),
                captured_at=now - timedelta(minutes=minutes),
            )
        )
    await db_session.flush()
    out = await get_whale_activity(db_session, "small-mkt")
    assert out["whale_count"] == 0


@pytest.mark.asyncio
async def test_whale_activity_never_raises_on_db_error():
    out = await get_whale_activity(_BrokenSession(), "x")
    assert out["tool"] == "get_whale_activity"
    assert "error" in out


# ── TASK 1: gather (concurrent) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gather_market_tools_runs_all_three(db_session):
    await _make_market(db_session, "gather-mkt")
    out = await gather_market_tools(db_session, "gather-mkt")
    assert set(out) == {
        "order_book",
        "price_history",
        "whale_activity",
        "depth_skew",
        "whale_concentration",
        "trade_intensity",
        "tools_used",
    }
    names = {t["tool"] for t in out["tools_used"]}
    assert names == {
        "get_order_book_summary",
        "get_price_history",
        "get_whale_activity",
        "get_depth_skew",
        "get_whale_concentration",
        "get_trade_intensity",
    }


# ── TASK 2: graph node ────────────────────────────────────────────────────────


def test_market_tools_node_registered_and_vetted():
    from app.agents.clone_service import VETTED_NODE_NAMES, validate_nodes
    from app.agents.graph import GRAPH_NODES

    assert "market_tools" in dict(GRAPH_NODES)
    assert "market_tools" in VETTED_NODE_NAMES
    assert validate_nodes(["data", "market_tools", "reasoning"]) == [
        "data",
        "market_tools",
        "reasoning",
    ]


def test_market_tools_node_injects_context_from_features():
    from app.agents.graph import AgentState, market_tools_node, reasoning_node

    tool_result = {
        "order_book": {"tool": "get_order_book_summary", "spread": 0.15},
        "whale_activity": {"tool": "get_whale_activity", "whale_count": 2},
        "price_history": {"tool": "get_price_history", "points": 3},
    }
    tool_result["tools_used"] = summarize_tools_used(tool_result)
    state = AgentState(market_slug="pm-x", features={"market_tools": tool_result})
    state = market_tools_node(state)
    assert "tools_used" in state.features
    # Downstream reasoning surfaces the tool figures.
    state = reasoning_node(state)
    assert "Tools:" in state.reasoning
    assert "spread 0.150" in state.reasoning
    assert "2 whale move(s)" in state.reasoning


def test_market_tools_node_calls_provider():
    from app.agents.graph import (
        AgentState,
        market_tools_node,
        set_market_tools_provider,
    )

    calls: list[str] = []

    def _provider(slug: str) -> dict:
        calls.append(slug)
        result = {
            "order_book": {"tool": "get_order_book_summary", "spread": 0.02},
            "price_history": {"tool": "get_price_history", "points": 1},
            "whale_activity": {"tool": "get_whale_activity", "whale_count": 0},
        }
        result["tools_used"] = summarize_tools_used(result)
        return result

    set_market_tools_provider(_provider)
    try:
        state = AgentState(market_slug="pm-y")
        state = market_tools_node(state)
    finally:
        set_market_tools_provider(None)

    assert calls == ["pm-y"]
    assert "market_tools" in state.features
    assert "tools_used" in state.features


def test_market_tools_node_is_context_only():
    """Guardrail: the tool node must not mutate probabilities or approval."""
    from app.agents.graph import AgentState, market_tools_node

    state = AgentState(
        market_slug="pm-z",
        predicted_prob=0.7,
        confidence=0.8,
        approved=True,
        features={"market_tools": {"order_book": {"spread": 0.1}}},
    )
    state = market_tools_node(state)
    assert state.predicted_prob == 0.7
    assert state.confidence == 0.8
    assert state.approved is True
    assert state.order_intent is None


def test_market_tools_node_provider_failure_is_isolated():
    from app.agents.graph import (
        AgentState,
        market_tools_node,
        set_market_tools_provider,
    )

    def _boom(_slug: str) -> dict:
        raise RuntimeError("provider exploded")

    set_market_tools_provider(_boom)
    try:
        state = AgentState(market_slug="pm-e")
        state = market_tools_node(state)  # must not raise
    finally:
        set_market_tools_provider(None)
    assert any("market_tools skipped" in e for e in state.errors)


# ── TASK 3: brief schema tools_used ───────────────────────────────────────────


def test_brief_schema_carries_tools_used_when_market_tools_ran():
    from app.agents.graph import run_agent_graph
    from app.schemas.brief import AnalystBriefModel

    tool_result = {
        "order_book": {"tool": "get_order_book_summary", "spread": 0.15, "best_bid": 0.4},
        "price_history": {"tool": "get_price_history", "points": 5, "last": 0.6},
        "whale_activity": {"tool": "get_whale_activity", "whale_count": 3},
    }
    tool_result["tools_used"] = summarize_tools_used(tool_result)
    # A full graph run threads the pre-injected tool output into state.features.
    state = run_agent_graph("pm-brief", {"market_tools": tool_result})
    tools_used = state.features["tools_used"]

    brief = AnalystBriefModel(
        market_slug="pm-brief",
        headline="Tool-informed read",
        body_markdown="Body grounded in live book + whale flow.",
        citations=[{"kind": "orderbook", "ref": "price 0.600"}],
        claim={"direction": "up", "horizon_minutes": 60, "confidence": 0.6},
        tools_used=tools_used,
    )
    dumped = brief.model_dump()
    assert dumped["tools_used"] is not None
    names = {t["tool"] for t in dumped["tools_used"]}
    assert names == {
        "get_order_book_summary",
        "get_price_history",
        "get_whale_activity",
        "get_depth_skew",
        "get_whale_concentration",
        "get_trade_intensity",
    }
    spread_entry = next(
        t for t in dumped["tools_used"] if t["tool"] == "get_order_book_summary"
    )
    assert spread_entry["spread"] == 0.15


def test_brief_schema_tools_used_optional():
    from app.schemas.brief import AnalystBriefModel

    brief = AnalystBriefModel(
        market_slug="pm-none",
        headline="No tools",
        body_markdown="Body.",
        citations=[{"kind": "model", "ref": "p=0.5"}],
        claim={"direction": "up", "horizon_minutes": 60, "confidence": 0.5},
    )
    assert brief.tools_used is None
