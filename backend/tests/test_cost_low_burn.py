"""COST-01 — low-burn mode: batched tick lookups + demand-paced polling.

The deployed free-tier stack pays for every Postgres round-trip (Neon CU-hours
+ egress). These tests pin the two cost fixes:

1. ``latest_implied_yes_by_slug`` — ONE window-function query replaces the
   per-market previous-price SELECT in the live tick pass.
2. ``persist_and_publish_tick(prev_yes=...)`` — a batch caller can supply the
   previous price and skip the per-slug SELECT entirely, with unchanged
   moved/alert semantics.
3. The activity tracker — monitoring probes (/health, /metrics) must NOT count
   as user demand, otherwise the uptime cron keeps the polling loop hot 24/7.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core import activity
from app.core.broadcast import hub
from app.db.models import OddsSnapshot
from app.services.live_price_tick import latest_implied_yes_by_slug
from app.workers.price_feed_worker import persist_and_publish_tick


def _snapshot(slug: str, yes: str, captured_at: datetime) -> OddsSnapshot:
    return OddsSnapshot(
        id=uuid4(),
        market_slug=slug,
        implied_yes=Decimal(yes),
        source="polymarket-live",
        captured_at=captured_at,
        book="polymarket",
        market_type="binary",
        outcome_name="Yes",
        price=Decimal(yes),
    )


@pytest.mark.asyncio
async def test_latest_implied_yes_by_slug_returns_newest_per_slug(db_session):
    now = datetime.now(UTC)
    db_session.add(_snapshot("cost-a", "0.30", now - timedelta(minutes=10)))
    db_session.add(_snapshot("cost-a", "0.55", now - timedelta(minutes=1)))
    db_session.add(_snapshot("cost-b", "0.80", now - timedelta(minutes=5)))
    await db_session.flush()

    result = await latest_implied_yes_by_slug(
        db_session, ["cost-a", "cost-b", "cost-missing"]
    )

    assert result["cost-a"] == pytest.approx(0.55)
    assert result["cost-b"] == pytest.approx(0.80)
    assert "cost-missing" not in result  # .get() -> None keeps first-tick semantics


@pytest.mark.asyncio
async def test_latest_implied_yes_by_slug_empty_input_skips_query(db_session):
    assert await latest_implied_yes_by_slug(db_session, []) == {}


class _NoSelectDB:
    """Fails the test if persist_and_publish_tick still runs its own SELECT."""

    def __init__(self) -> None:
        self.added: list = []

    async def scalar(self, *_args, **_kwargs):
        raise AssertionError(
            "prev_yes was supplied — the per-slug SELECT must be skipped"
        )

    def add(self, obj) -> None:
        self.added.append(obj)


@pytest.mark.asyncio
async def test_supplied_prev_yes_skips_select_and_keeps_semantics(monkeypatch):
    published: list[dict] = []
    monkeypatch.setattr(
        hub, "publish", AsyncMock(side_effect=lambda _slug, p: published.append(p))
    )

    db = _NoSelectDB()
    moved = await persist_and_publish_tick(
        db, slug="m", yes=0.50, source="polymarket-live", prev_yes=0.40
    )
    assert moved is True
    assert len(db.added) == 1
    assert published[-1]["alert"] is True  # 10-point move

    db = _NoSelectDB()
    moved = await persist_and_publish_tick(
        db, slug="m", yes=0.4001, source="polymarket-live", prev_yes=0.40
    )
    assert moved is False  # below epsilon -> no persist
    assert db.added == []

    db = _NoSelectDB()
    moved = await persist_and_publish_tick(
        db, slug="m", yes=0.40, source="polymarket-live", prev_yes=None
    )
    assert moved is True  # explicit None = known first tick
    assert published[-1]["alert"] is False


def test_activity_monitoring_paths_are_exempt():
    assert activity.is_monitoring_path("/health")
    assert activity.is_monitoring_path("/metrics")
    assert activity.is_monitoring_path("/metrics/prometheus")
    assert not activity.is_monitoring_path("/api/v1/markets")
    assert not activity.is_monitoring_path("/healthcheck-lookalike")


def test_activity_window(monkeypatch):
    activity.reset_for_tests()
    assert activity.is_active(300) is False  # boot state: idle until real demand

    clock = {"now": 1000.0}
    monkeypatch.setattr(activity.time, "monotonic", lambda: clock["now"])
    activity.mark_activity()
    assert activity.is_active(300) is True

    clock["now"] += 299
    assert activity.is_active(300) is True
    clock["now"] += 2
    assert activity.is_active(300) is False
    activity.reset_for_tests()


def test_live_tick_demand_counts_ws_subscribers():
    from app.main import _live_tick_demand

    activity.reset_for_tests()
    assert _live_tick_demand() is False

    queue = hub.subscribe("cost-demand-slug")
    try:
        assert _live_tick_demand() is True
    finally:
        hub.unsubscribe("cost-demand-slug", queue)
    assert _live_tick_demand() is False
