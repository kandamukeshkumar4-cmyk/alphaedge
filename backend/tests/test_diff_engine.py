"""T03 — snapshot diff engine: pure boundaries, service state, persistence."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.models import DomainEvent, Market, MarketStatus, SignalEvent
from app.signals.diff_engine import (
    DeltaKind,
    DiffEngineService,
    DiffThresholds,
    InMemorySnapshotStateStore,
    MarketSnapshotState,
    compute_market_delta,
    persist_deltas,
)


async def _seed_market(db, slug="m"):
    db.add(
        Market(
            id=uuid4(), slug=slug, title="t", question="q",
            status=MarketStatus.OPEN, source="polymarket", category="Sports",
        )
    )
    await db.flush()

THR = DiffThresholds(price_jump_bps=100.0, orderbook_flip_ratio=1.0, volume_surge_min=10_000.0)
# price_jump_prob = 0.01


def _state(slug="m", **kw) -> MarketSnapshotState:
    return MarketSnapshotState(market_slug=slug, source="kalshi.ws", **kw)


# --- price_jump boundaries -------------------------------------------------


def test_price_jump_exactly_at_threshold_does_not_fire():
    prev = _state(implied_yes=0.50)
    curr = _state(implied_yes=0.51)  # exactly 0.01 = 100 bps
    assert compute_market_delta(prev, curr, THR) == []


def test_price_jump_strictly_over_fires_up():
    prev = _state(implied_yes=0.50)
    curr = _state(implied_yes=0.5101)  # > 0.01
    deltas = compute_market_delta(prev, curr, THR)
    assert len(deltas) == 1
    assert deltas[0].kind is DeltaKind.PRICE_JUMP
    assert deltas[0].direction == "up"


def test_price_jump_direction_down():
    deltas = compute_market_delta(_state(implied_yes=0.50), _state(implied_yes=0.48), THR)
    assert deltas[0].direction == "down"
    assert deltas[0].magnitude == pytest.approx(0.02)


def test_price_jump_skipped_when_price_missing():
    prev = _state(implied_yes=None, volume=1.0)
    curr = _state(implied_yes=0.9, volume=1.0)
    assert compute_market_delta(prev, curr, THR) == []


# --- orderbook_flip --------------------------------------------------------


def test_orderbook_flip_fires_on_cross():
    prev = _state(bid_size=100, ask_size=200)  # ratio 0.5 < 1
    curr = _state(bid_size=300, ask_size=200)  # ratio 1.5 > 1 -> crossed
    deltas = compute_market_delta(prev, curr, THR)
    assert len(deltas) == 1
    assert deltas[0].kind is DeltaKind.ORDERBOOK_FLIP
    assert deltas[0].direction == "bid_dominant"


def test_orderbook_flip_no_cross_no_fire():
    prev = _state(bid_size=100, ask_size=200)  # 0.5
    curr = _state(bid_size=150, ask_size=200)  # 0.75 still < 1
    assert compute_market_delta(prev, curr, THR) == []


def test_orderbook_flip_exactly_at_boundary_does_not_fire():
    prev = _state(bid_size=100, ask_size=200)  # 0.5
    curr = _state(bid_size=200, ask_size=200)  # exactly 1.0 -> not strictly crossed
    assert compute_market_delta(prev, curr, THR) == []


# --- volume_surge ----------------------------------------------------------


def test_volume_surge_strictly_over_fires():
    deltas = compute_market_delta(_state(volume=0.0), _state(volume=10_000.01), THR)
    assert len(deltas) == 1 and deltas[0].kind is DeltaKind.VOLUME_SURGE


def test_volume_surge_exactly_at_threshold_does_not_fire():
    assert compute_market_delta(_state(volume=0.0), _state(volume=10_000.0), THR) == []


# --- service: seed / idempotent / merge ------------------------------------


@pytest.mark.asyncio
async def test_first_observation_seeds_and_returns_empty():
    svc = DiffEngineService(store=InMemorySnapshotStateStore(), thresholds=THR)
    assert await svc.observe("m", source="kalshi.ws", implied_yes=0.5) == []
    stored = await svc.store.get("m")
    assert stored is not None and stored.implied_yes == 0.5


@pytest.mark.asyncio
async def test_identical_snapshot_is_idempotent():
    svc = DiffEngineService(store=InMemorySnapshotStateStore(), thresholds=THR)
    await svc.observe("m", implied_yes=0.5)
    assert await svc.observe("m", implied_yes=0.5) == []


@pytest.mark.asyncio
async def test_tick_only_update_inherits_orderbook_and_can_flip():
    svc = DiffEngineService(store=InMemorySnapshotStateStore(), thresholds=THR)
    # seed with full state (ratio 0.5)
    await svc.observe("m", implied_yes=0.5, bid_size=100, ask_size=200)
    # an orderbook-only update that flips the ratio to 1.5
    deltas = await svc.observe("m", bid_size=300, ask_size=200)
    kinds = {d.kind for d in deltas}
    assert DeltaKind.ORDERBOOK_FLIP in kinds


@pytest.mark.asyncio
async def test_big_price_move_fires_price_jump_via_service():
    svc = DiffEngineService(store=InMemorySnapshotStateStore(), thresholds=THR)
    await svc.observe("m", implied_yes=0.50)
    deltas = await svc.observe("m", implied_yes=0.60)
    assert any(d.kind is DeltaKind.PRICE_JUMP for d in deltas)


# --- source discontinuity (E16) --------------------------------------------


def test_price_jump_suppressed_when_prev_source_is_seed():
    # seed placeholder -> live is a source discontinuity, not a market move.
    prev = MarketSnapshotState(market_slug="m", source="polymarket.gamma-seed", implied_yes=0.15)
    curr = MarketSnapshotState(market_slug="m", source="polymarket.gamma", implied_yes=0.995)
    assert compute_market_delta(prev, curr, THR) == []


def test_price_jump_suppressed_when_curr_source_is_fallback():
    prev = MarketSnapshotState(market_slug="m", source="polymarket.gamma", implied_yes=0.50)
    curr = MarketSnapshotState(market_slug="m", source="polymarket-fallback", implied_yes=0.90)
    assert compute_market_delta(prev, curr, THR) == []


def test_price_jump_fires_between_two_live_sources():
    # A genuine move between authoritative observations still fires.
    prev = _state(implied_yes=0.50)  # source="kalshi.ws"
    curr = _state(implied_yes=0.60)
    deltas = compute_market_delta(prev, curr, THR)
    assert len(deltas) == 1 and deltas[0].kind is DeltaKind.PRICE_JUMP


# --- persistence -----------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_deltas_writes_signal_and_domain_events(db_session):
    prev = _state(implied_yes=0.50)
    curr = _state(implied_yes=0.60)
    deltas = compute_market_delta(prev, curr, THR)
    assert deltas

    await persist_deltas(db_session, deltas)
    await db_session.flush()

    sig_count = await db_session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.signal_type == "delta:price_jump"
        )
    )
    assert sig_count == 1
    dom_count = await db_session.scalar(
        select(func.count()).select_from(DomainEvent).where(
            DomainEvent.event_type == "delta.price_jump"
        )
    )
    assert dom_count == 1


@pytest.mark.asyncio
async def test_persist_deltas_require_market_drops_orphan_slug(db_session):
    # With require_market=True (the diff-engine price path), a delta for a slug
    # with no matching Market must NOT persist — this is the guard against the
    # stale in-memory ghost that emitted bogus, unjoinable France price jumps
    # (E15/E16). A real market seeded under the same slug persists normally.
    prev = _state(slug="ghost-slug", implied_yes=0.50)
    curr = _state(slug="ghost-slug", implied_yes=0.60)
    deltas = compute_market_delta(prev, curr, THR)
    assert deltas

    await persist_deltas(db_session, deltas, require_market=True)
    await db_session.flush()
    assert await db_session.scalar(select(func.count()).select_from(SignalEvent)) == 0

    # Same delta, but now the market exists → it persists.
    await _seed_market(db_session, "ghost-slug")
    await persist_deltas(db_session, deltas, require_market=True)
    await db_session.flush()
    assert await db_session.scalar(select(func.count()).select_from(SignalEvent)) == 1


@pytest.mark.asyncio
async def test_persist_deltas_empty_is_noop(db_session):
    await persist_deltas(db_session, [])
    await db_session.flush()
    count = await db_session.scalar(select(func.count()).select_from(SignalEvent))
    assert count == 0
