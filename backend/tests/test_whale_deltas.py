"""T05 — whale position diffing + end-to-end whale_delta into the alignment scorer."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.data.connectors.polymarket_data_api import WalletPositionRow
from app.db.models import SignalEvent, WalletPositionSnapshot
from app.signals.diff_engine import DeltaKind
from app.signals.smart_money import (
    WhaleAction,
    WhalePositionState,
    diff_whale_positions,
)


def _state(slug, outcome="YES", size="100"):
    return WhalePositionState(market_slug=slug, outcome=outcome, size=Decimal(size))


def test_new_position_is_an_add_up_for_yes():
    deltas = diff_whale_positions([], [_state("m", "YES", "100")])
    assert len(deltas) == 1
    assert deltas[0].action is WhaleAction.ADD
    assert deltas[0].direction == "up"


def test_new_no_position_is_down():
    deltas = diff_whale_positions([], [_state("m", "NO", "100")])
    assert deltas[0].direction == "down"


def test_increase_size_is_add():
    deltas = diff_whale_positions([_state("m", "YES", "100")], [_state("m", "YES", "150")])
    assert deltas[0].action is WhaleAction.ADD
    assert deltas[0].size_change == Decimal("50")


def test_unchanged_position_no_delta():
    assert diff_whale_positions([_state("m", "YES", "100")], [_state("m", "YES", "100")]) == []


def test_decrease_size_is_not_an_add():
    # size dropped but position not exited -> no add (only increases signal conviction)
    deltas = diff_whale_positions([_state("m", "YES", "100")], [_state("m", "YES", "60")])
    assert deltas == []


def test_full_exit_is_exit_opposite_direction():
    deltas = diff_whale_positions([_state("m", "YES", "100")], [])
    assert deltas[0].action is WhaleAction.EXIT
    assert deltas[0].direction == "down"  # exiting YES removes bullish support


def test_flip_side_is_flip():
    deltas = diff_whale_positions([_state("m", "YES", "100")], [_state("m", "NO", "80")])
    assert len(deltas) == 1
    assert deltas[0].action is WhaleAction.FLIP
    assert deltas[0].direction == "down"  # now building NO


# --- end-to-end accept: qualified wallet adds size -> whale_delta reaches scorer ---


@pytest.mark.asyncio
async def test_snapshot_and_diff_emits_whale_delta(db_session):
    from app.services.whale_tracker_service import WhaleTrackerService

    service = WhaleTrackerService(db_session)
    positions_v1 = [
        WalletPositionRow("0xw", "0xm", "pm-fed", "YES", Decimal("100"), Decimal("0.5"))
    ]
    # first snapshot: seeds state, no prior -> add delta (new position)
    first = await service.snapshot_and_diff("0xw", positions_v1)
    assert len(first) == 1 and first[0].kind is DeltaKind.WHALE_DELTA

    # second snapshot: same size -> no delta
    second = await service.snapshot_and_diff("0xw", positions_v1)
    assert second == []

    # third: larger size -> whale_delta (add)
    positions_v2 = [
        WalletPositionRow("0xw", "0xm", "pm-fed", "YES", Decimal("300"), Decimal("0.5"))
    ]
    third = await service.snapshot_and_diff("0xw", positions_v2)
    assert len(third) == 1
    assert third[0].direction == "up"

    await db_session.flush()
    # snapshots persisted (3 rows for this wallet+market)
    snap_count = await db_session.scalar(
        select(func.count()).select_from(WalletPositionSnapshot).where(
            WalletPositionSnapshot.wallet_address == "0xw"
        )
    )
    assert snap_count == 3
    # whale_delta persisted to signal_events
    sig_count = await db_session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.signal_type == "delta:whale_delta"
        )
    )
    assert sig_count >= 2  # first add + third add
