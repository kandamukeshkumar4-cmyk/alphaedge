"""T04 — alignment scorer: layer counting, dedupe, window expiry, persistence."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db.models import DomainEvent, SignalEvent
from app.signals.alignment import (
    AlignmentLayer,
    AlignmentScorer,
    AlignmentThresholds,
    delta_to_layer_vote,
    persist_alignment,
)
from app.signals.diff_engine import DeltaEvent, DeltaKind

T0 = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
THR = AlignmentThresholds(window_sec=600.0, min_score=3.0, min_layers=3)


def _delta(kind: DeltaKind, direction: str, slug="m") -> DeltaEvent:
    return DeltaEvent(
        market_slug=slug,
        source="kalshi.ws",
        kind=kind,
        direction=direction,
        magnitude=1.0,
        detail={},
        occurred_ts=T0,
    )


PRICE_UP = _delta(DeltaKind.PRICE_JUMP, "up")
WHALE_UP = _delta(DeltaKind.WHALE_DELTA, "up")
NEWS_UP = _delta(DeltaKind.NEWS_ARRIVAL, "up")
NEWS_DOWN = _delta(DeltaKind.NEWS_ARRIVAL, "down")


# --- layer/vote mapping ----------------------------------------------------


def test_orderbook_flip_maps_to_price_layer_direction():
    up = delta_to_layer_vote(_delta(DeltaKind.ORDERBOOK_FLIP, "bid_dominant"))
    down = delta_to_layer_vote(_delta(DeltaKind.ORDERBOOK_FLIP, "ask_dominant"))
    assert up == (AlignmentLayer.PRICE, "up")
    assert down == (AlignmentLayer.PRICE, "down")


def test_volume_surge_is_not_a_layer_vote():
    assert delta_to_layer_vote(_delta(DeltaKind.VOLUME_SURGE, "up")) is None


# --- core alignment cases (spec) -------------------------------------------


def test_two_layers_does_not_trigger():
    scorer = AlignmentScorer(THR)
    assert scorer.observe_deltas([PRICE_UP, WHALE_UP], now=T0) is None


def test_three_layers_same_direction_triggers():
    scorer = AlignmentScorer(THR)
    score = scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_UP], now=T0)
    assert score is not None
    assert score.direction == "up"
    assert score.layers_firing == frozenset(
        {AlignmentLayer.PRICE, AlignmentLayer.WHALE, AlignmentLayer.NEWS}
    )
    assert score.score == 3.0


def test_three_layers_mixed_direction_does_not_trigger():
    scorer = AlignmentScorer(THR)
    # price up, whale up, news down -> max 2 in one direction
    assert scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_DOWN], now=T0) is None


def test_price_layer_counts_once_even_with_many_deltas():
    scorer = AlignmentScorer(THR)
    # two price deltas + one whale = still only 2 distinct layers
    assert (
        scorer.observe_deltas(
            [PRICE_UP, _delta(DeltaKind.ORDERBOOK_FLIP, "bid_dominant"), WHALE_UP],
            now=T0,
        )
        is None
    )


def test_model_layer_as_fourth_vote_completes_alignment():
    scorer = AlignmentScorer(THR)
    score = scorer.observe_deltas([PRICE_UP, WHALE_UP], model_vote=("m", "up"), now=T0)
    assert score is not None
    assert AlignmentLayer.MODEL in score.layers_firing
    assert score.score == 3.0


# --- dedupe + window expiry ------------------------------------------------


def test_dedupe_fires_once_within_window():
    scorer = AlignmentScorer(THR)
    first = scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_UP], now=T0)
    assert first is not None
    # another up delta seconds later — still same direction, must NOT re-fire
    again = scorer.observe_deltas([PRICE_UP], now=T0 + timedelta(seconds=30))
    assert again is None


def test_window_expiry_resets_and_allows_new_trigger():
    scorer = AlignmentScorer(THR)
    assert scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_UP], now=T0) is not None
    # after the window fully passes, votes expire and dedupe resets
    later = T0 + timedelta(seconds=601)
    p = _delta(DeltaKind.PRICE_JUMP, "up")
    w = _delta(DeltaKind.WHALE_DELTA, "up")
    n = _delta(DeltaKind.NEWS_ARRIVAL, "up")
    for d in (p, w, n):
        object.__setattr__(d, "occurred_ts", later)
    assert scorer.observe_deltas([p, w, n], now=later) is not None


def test_partial_expiry_below_threshold_resets_dedupe():
    # Fire up (3 layers). Let whale+news expire while price keeps ticking (window
    # never fully empties). When all 3 re-align later, it must fire again.
    scorer = AlignmentScorer(THR)
    assert scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_UP], now=T0) is not None
    # +400s: only a price tick — whale/news (from T0) still within 600s window, so
    # still aligned & deduped
    assert scorer.observe_deltas([PRICE_UP], now=T0 + timedelta(seconds=400)) is None
    # +700s: T0 whale/news expired; a lone price tick -> score drops below threshold
    assert scorer.observe_deltas([PRICE_UP], now=T0 + timedelta(seconds=700)) is None
    # now re-align all 3 at +720s -> episode reset -> fires again
    p = _delta(DeltaKind.PRICE_JUMP, "up")
    w = _delta(DeltaKind.WHALE_DELTA, "up")
    n = _delta(DeltaKind.NEWS_ARRIVAL, "up")
    assert scorer.observe_deltas([p, w, n], now=T0 + timedelta(seconds=720)) is not None


def test_opposite_direction_can_trigger_after_first():
    scorer = AlignmentScorer(THR)
    assert scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_UP], now=T0) is not None
    # three down votes in the same window -> new dominant direction fires
    pd = _delta(DeltaKind.PRICE_JUMP, "down")
    wd = _delta(DeltaKind.WHALE_DELTA, "down")
    nd = _delta(DeltaKind.NEWS_ARRIVAL, "down")
    score = scorer.observe_deltas([pd, wd, nd], now=T0 + timedelta(seconds=10))
    assert score is not None and score.direction == "down"


# --- persistence (accept: exactly one analyst.trigger) ---------------------


@pytest.mark.asyncio
async def test_persist_alignment_writes_signal_and_trigger(db_session):
    scorer = AlignmentScorer(THR)
    score = scorer.observe_deltas([PRICE_UP, WHALE_UP, NEWS_UP], now=T0)
    assert score is not None

    await persist_alignment(db_session, score)
    await db_session.flush()

    sig = await db_session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.signal_type == "alignment"
        )
    )
    assert sig == 1
    trig = await db_session.scalar(
        select(func.count()).select_from(DomainEvent).where(
            DomainEvent.event_type == "analyst.trigger"
        )
    )
    assert trig == 1
    row = await db_session.scalar(
        select(SignalEvent).where(SignalEvent.signal_type == "alignment")
    )
    assert row.headline_eligible is True
    assert row.payload["direction"] == "up"
    assert sorted(row.payload["layers"]) == ["news", "price", "whale"]
