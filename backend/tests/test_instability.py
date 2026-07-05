"""T13 — instability index: decay math, threshold boundary, DeltaEvent emission."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import SignalEvent
from app.signals.event_taxonomy import EventCategory
from app.signals.instability import (
    InstabilityService,
    TaggedItem,
    crosses_threshold,
    rolling_instability_score,
    tag_news_item,
)

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)


def _item(cat, hours_ago, region="MidEast"):
    return TaggedItem(region=region, category=cat, ts=NOW - timedelta(hours=hours_ago))


# --- decay + score ---------------------------------------------------------


def test_no_news_region_scores_zero():
    assert rolling_instability_score([], now=NOW) == 0.0


def test_recent_high_severity_scores_higher_than_old():
    recent = rolling_instability_score([_item(EventCategory.MILITARY, 0)], now=NOW)
    old = rolling_instability_score(
        [_item(EventCategory.MILITARY, 20)], now=NOW, half_life_hours=6
    )
    assert recent > old > 0.0


def test_items_outside_window_ignored():
    # item 30h ago with 24h window -> excluded -> score 0
    assert rolling_instability_score(
        [_item(EventCategory.MILITARY, 30)], now=NOW, window_hours=24
    ) == 0.0


def test_decay_halves_at_half_life():
    now_item = rolling_instability_score(
        [_item(EventCategory.MILITARY, 0)], now=NOW, half_life_hours=12
    )
    half_life_item = rolling_instability_score(
        [_item(EventCategory.MILITARY, 12)], now=NOW, half_life_hours=12
    )
    assert half_life_item == pytest.approx(now_item / 2, rel=0.02)


def test_score_capped_at_100():
    many = [_item(EventCategory.MILITARY, 0) for _ in range(50)]
    assert rolling_instability_score(many, now=NOW) == 100.0


# --- threshold crossing ----------------------------------------------------


def test_threshold_boundary_exactly_at_does_not_fire():
    # exactly at threshold is NOT an upward cross (strictly over required)
    assert crosses_threshold(40.0, 50.0, threshold=50.0) is False


def test_threshold_strictly_over_fires():
    assert crosses_threshold(40.0, 50.1, threshold=50.0) is True


def test_no_cross_when_already_above():
    assert crosses_threshold(60.0, 70.0, threshold=50.0) is False


def test_tag_news_item():
    tagged = tag_news_item("Missile strike in Israel", NOW)
    assert tagged.category == EventCategory.MILITARY
    assert tagged.region == "MidEast"


# --- service: emit DeltaEvent on cross, flag-gated --------------------------


def _settings(enabled=True, threshold=50.0):
    return SimpleNamespace(
        instability_enabled=enabled,
        instability_window_hours=24.0,
        instability_half_life_hours=12.0,
        instability_threshold=threshold,
    )


@pytest.mark.asyncio
async def test_disabled_is_noop(db_session):
    service = InstabilityService(db_session, settings=_settings(enabled=False))
    result = await service.update_region(
        "MidEast", [_item(EventCategory.MILITARY, 0)] * 10, "pm-geo", now=NOW
    )
    assert result is None
    await db_session.flush()
    count = await db_session.scalar(select(func.count()).select_from(SignalEvent))
    assert count == 0


@pytest.mark.asyncio
async def test_upward_cross_emits_instability_shift(db_session):
    service = InstabilityService(db_session, settings=_settings(threshold=30.0))
    # many recent high-severity items -> score well above 30 -> cross from prev 0
    await service.update_region(
        "MidEast", [_item(EventCategory.MILITARY, 0)] * 5, "pm-geo", now=NOW
    )
    await db_session.flush()
    shift = await db_session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.signal_type == "delta:instability_shift"
        )
    )
    inst = await db_session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.signal_type == "instability"
        )
    )
    assert shift == 1 and inst == 1
