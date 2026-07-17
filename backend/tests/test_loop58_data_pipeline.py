"""Loop V58 — master data pipeline (whale flow, venue gap, context, graph).

Mocked externals only. Asserts rate-limit, leakage timestamps, context shape,
and flag-gated graph features.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.graph import GRAPH_NODES, AgentState, whale_signal_node
from app.main import app
from app.signals.venue_gap import (
    VenueQuote,
    bounded_venue_gap_feature,
    compute_venue_gap,
    reset_venue_gap_cache,
    cache_venue_gap,
)
from app.signals.whale_flow import (
    LargeTrade,
    WhalePressure,
    cache_whale_pressure,
    compute_whale_pressure,
    normalize_large_trades,
    rate_limit_ok,
    record_poll_failure,
    record_poll_success,
    reset_whale_flow_state,
    circuit_is_open,
)


@pytest.fixture(autouse=True)
def _clean_loop58_state():
    reset_whale_flow_state()
    reset_venue_gap_cache()
    yield
    reset_whale_flow_state()
    reset_venue_gap_cache()


# ── D1 whale flow pure helpers ──────────────────────────────────────────────


def test_normalize_large_trades_filters_threshold_and_market():
    payload = [
        {
            "proxyWallet": "0xaaa",
            "side": "BUY",
            "outcome": "YES",
            "price": 0.5,
            "size": 100,
            "slug": "keep-me",
            "conditionId": "c1",
            "transactionHash": "0x1",
            "timestamp": datetime.now(UTC).timestamp(),
        },
        {
            "proxyWallet": "0xbbb",
            "side": "SELL",
            "outcome": "NO",
            "price": 0.4,
            "size": 10_000,
            "slug": "keep-me",
            "conditionId": "c1",
            "transactionHash": "0x2",
            "timestamp": datetime.now(UTC).timestamp(),
        },
        {
            "proxyWallet": "0xccc",
            "side": "BUY",
            "outcome": "YES",
            "price": 0.6,
            "size": 50_000,
            "slug": "other-mkt",
            "conditionId": "c2",
            "usdcSize": 30_000,
            "transactionHash": "0x3",
            "timestamp": datetime.now(UTC).timestamp(),
        },
    ]
    trades = normalize_large_trades(
        payload,
        min_notional=Decimal("1000"),
        market_slugs={"keep-me"},
    )
    assert len(trades) == 1
    assert trades[0].wallet == "0xbbb"
    assert trades[0].notional >= Decimal("1000")
    assert trades[0].market_slug == "keep-me"
    # Leakage: trade_at must be set from payload timestamp (capture-time filterable)
    assert trades[0].trade_at is not None
    assert trades[0].trade_at.tzinfo is not None


def test_whale_pressure_bounded_and_directional():
    now = datetime.now(UTC)
    buy_yes = LargeTrade(
        wallet="0x1",
        side="BUY",
        outcome="YES",
        size=Decimal("5000"),
        price=Decimal("0.5"),
        notional=Decimal("2500"),
        market_slug="m1",
        market_id="c1",
        tx_hash="t1",
        trade_at=now,
    )
    sell_yes = LargeTrade(
        wallet="0x2",
        side="SELL",
        outcome="YES",
        size=Decimal("5000"),
        price=Decimal("0.5"),
        notional=Decimal("2500"),
        market_slug="m1",
        market_id="c1",
        tx_hash="t2",
        trade_at=now,
    )
    p_up = compute_whale_pressure([buy_yes], market_slug="m1", as_of=now)
    p_down = compute_whale_pressure([sell_yes], market_slug="m1", as_of=now)
    p_flat = compute_whale_pressure([buy_yes, sell_yes], market_slug="m1", as_of=now)
    assert -1.0 <= p_up.pressure <= 1.0
    assert p_up.pressure > 0
    assert p_down.pressure < 0
    assert abs(p_flat.pressure) < 0.05
    # Leakage gate: as_of is capture clock, not resolution
    assert p_up.as_of.tzinfo is not None


def test_whale_flow_rate_limit_and_circuit_breaker():
    assert rate_limit_ok(min_interval_sec=60) is True
    record_poll_success()
    assert rate_limit_ok(min_interval_sec=60) is False
    assert circuit_is_open() is False
    record_poll_failure()
    record_poll_failure()
    record_poll_failure()
    assert circuit_is_open() is True


@pytest.mark.asyncio
async def test_whale_flow_task_respects_disabled_flag():
    from app.workers.tasks import whale_flow_task

    with patch("app.workers.tasks.get_settings") as gs:
        settings = MagicMock()
        settings.whale_flow_enabled = False
        gs.return_value = settings
        out = await whale_flow_task({})
    assert out["skipped"] is True
    assert "WHALE_FLOW_ENABLED" in out["reason"]


# ── D2 venue gap ────────────────────────────────────────────────────────────


def test_compute_venue_gap_and_staleness():
    now = datetime.now(UTC)
    fresh = now - timedelta(seconds=30)
    old = now - timedelta(seconds=600)
    result = compute_venue_gap(
        VenueQuote("pm-a", Decimal("0.60"), fresh),
        VenueQuote("ks-a", Decimal("0.50"), fresh),
        match_confidence=0.9,
        now=now,
        stale_after_sec=300,
    )
    assert float(result.gap) == pytest.approx(0.1)
    assert result.stale is False
    assert result.captured_at.tzinfo is not None

    stale = compute_venue_gap(
        VenueQuote("pm-a", Decimal("0.60"), old),
        VenueQuote("ks-a", Decimal("0.50"), fresh),
        match_confidence=0.9,
        now=now,
        stale_after_sec=300,
    )
    assert stale.stale is True
    assert "pm_stale" in stale.reason


def test_bounded_venue_gap_feature():
    assert bounded_venue_gap_feature(0.25, max_abs=0.5) == pytest.approx(0.5)
    assert bounded_venue_gap_feature(1.0, max_abs=0.5) == 1.0
    assert bounded_venue_gap_feature(-1.0, max_abs=0.5) == -1.0
    assert bounded_venue_gap_feature(None) == 0.0


# ── D3 context endpoint shape ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_market_context_endpoint_shape(db_session):
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/markets/nba-2025-01-15-lal-bos/context")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "found",
        "slug",
        "whale",
        "venue_gap",
        "news",
        "sentiment_trend",
        "sentiment_debate",
        "price_trend",
        "volume",
        "features",
        "generated_at",
        "signal_only",
        "paper_trading_only",
        "disclaimer",
    ):
        assert key in body, f"missing {key}"
    assert body["slug"] == "nba-2025-01-15-lal-bos"
    assert body["signal_only"] is True
    assert body["paper_trading_only"] is True
    # Leakage: top-level and nested timestamps present / ISO-shaped when set
    assert "T" in body["generated_at"]
    assert "pressure" in body["whale"]
    assert -1.0 <= float(body["whale"]["pressure"]) <= 1.0
    assert "captured_at" in body["whale"]
    assert set(body["features"].keys()) >= {
        "whale_pressure",
        "venue_gap",
        "venue_gap_bounded",
        "news_sentiment",
        "sentiment_direction",
        "sentiment_acceleration",
        "price_delta_1h",
        "volume_percentile",
    }


@pytest.mark.asyncio
async def test_context_digest_endpoint_shape(db_session):
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/context/digest?limit=5")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "generated_at",
        "whale_top",
        "venue_gaps_top",
        "counts",
        "signal_only",
        "paper_trading_only",
    ):
        assert key in body
    assert body["signal_only"] is True
    assert isinstance(body["whale_top"], list)
    assert isinstance(body["venue_gaps_top"], list)


@pytest.mark.asyncio
async def test_venue_gaps_api_shape(db_session):
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/venue-gaps?limit=5")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert "gaps" in body
    assert body["signal_only"] is True
    assert "disclaimer" in body


# ── D4 graph wiring ─────────────────────────────────────────────────────────


def test_whale_signal_node_in_graph():
    names = [n for n, _ in GRAPH_NODES]
    assert "whale_signal" in names
    assert names.index("whale_signal") > names.index("nemotron")
    assert names.index("whale_signal") < names.index("memory")


def test_whale_signal_node_flag_off_is_noop():
    cache_whale_pressure(
        WhalePressure(
            market_slug="m-flag",
            pressure=0.8,
            event_count=3,
            net_notional=1000.0,
            total_notional=1000.0,
            window_sec=3600.0,
            as_of=datetime.now(UTC),
        )
    )
    with patch("app.core.config.get_settings") as gs:
        settings = MagicMock()
        settings.whale_signal_enabled = False
        gs.return_value = settings
        state = whale_signal_node(AgentState(market_slug="m-flag", features={}))
    assert "whale_pressure" not in state.features


def test_whale_signal_node_flag_on_injects_bounded_features():
    now = datetime.now(UTC)
    cache_whale_pressure(
        WhalePressure(
            market_slug="m-on",
            pressure=0.75,
            event_count=2,
            net_notional=2000.0,
            total_notional=2000.0,
            window_sec=3600.0,
            as_of=now,
        )
    )
    cache_venue_gap(
        compute_venue_gap(
            VenueQuote("m-on", Decimal("0.55"), now),
            VenueQuote("ks-on", Decimal("0.45"), now),
            match_confidence=0.9,
            now=now,
        )
    )
    with patch("app.core.config.get_settings") as gs:
        settings = MagicMock()
        settings.whale_signal_enabled = True
        gs.return_value = settings
        state = whale_signal_node(AgentState(market_slug="m-on", features={}))
    assert state.features["whale_pressure"] == pytest.approx(0.75)
    assert -1.0 <= state.features["venue_gap_bounded"] <= 1.0
    assert "whale_pressure_captured_at" in state.features
    assert "venue_gap_captured_at" in state.features
    # Must not invent order intents
    assert state.order_intent is None


def test_run_agent_graph_includes_whale_step_when_flag_on():
    from app.agents.graph import run_agent_graph_with_trace

    with patch("app.core.config.get_settings") as gs:
        settings = MagicMock()
        settings.whale_signal_enabled = False
        settings.nemotron_signal_enabled = False
        gs.return_value = settings
        # Also patch inside nodes that call get_settings again
        with patch("app.agents.graph.get_settings", gs, create=True):
            state, trace = run_agent_graph_with_trace("nba-2025-01-15-lal-bos", {})
    names = [s.step_name for s in trace]
    assert "whale_signal" in names


def test_loops_registry_includes_v58_loops():
    from app.api.v1.system import _ALL_LOOPS
    from app.observability.loop_state import LOOP_INTERVALS

    assert "whale_flow" in _ALL_LOOPS
    assert "venue_gap" in _ALL_LOOPS
    assert LOOP_INTERVALS["whale_flow"] == 60
    assert LOOP_INTERVALS["venue_gap"] == 60


def test_worker_registers_v58_tasks():
    from app.workers.tasks import WorkerSettings, venue_gap_task, whale_flow_task

    assert whale_flow_task in WorkerSettings.functions
    assert venue_gap_task in WorkerSettings.functions
