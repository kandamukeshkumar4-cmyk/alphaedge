"""Loop V59 H3 — reversible emergency halt evaluators."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models import OddsSnapshot
from app.services.heartbeat_decision import (
    HeartbeatAction,
    HeartbeatRules,
    PositionSnapshot,
    decide,
)
from app.services.heartbeat_halts import (
    compose_halt_flags,
    evaluate_daily_loss_halts,
    evaluate_price_feed_staleness,
    get_halt_state,
    halt_transition_log_rows,
    reset_halt_state,
)


@pytest.fixture(autouse=True)
def _clear_halts():
    reset_halt_state()
    yield
    reset_halt_state()


_NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
_RULES = HeartbeatRules(staleness_sec=120.0)


@pytest.mark.asyncio
async def test_price_feed_staleness_engages_and_clears(db_session):
    db_session.add(
        OddsSnapshot(
            market_slug="nba-2025-01-15-lal-bos",
            implied_yes=Decimal("0.55"),
            source="fixture",
            captured_at=_NOW - timedelta(seconds=200),
        )
    )
    await db_session.commit()

    stale = await evaluate_price_feed_staleness(
        db_session, now=_NOW, stale_after_sec=120.0
    )
    assert stale is True
    assert get_halt_state().price_feed_stale is True
    rows = halt_transition_log_rows(_NOW)
    assert any(r["action_taken"] == "halt_engaged" for r in rows)

    db_session.add(
        OddsSnapshot(
            market_slug="nba-2025-01-15-lal-bos",
            implied_yes=Decimal("0.56"),
            source="fixture",
            captured_at=_NOW - timedelta(seconds=5),
        )
    )
    await db_session.commit()
    stale2 = await evaluate_price_feed_staleness(
        db_session, now=_NOW, stale_after_sec=120.0
    )
    assert stale2 is False
    assert get_halt_state().price_feed_stale is False
    rows2 = halt_transition_log_rows(_NOW)
    assert any(r["action_taken"] == "halt_cleared" for r in rows2)


@pytest.mark.asyncio
async def test_daily_loss_halt_empty_when_no_loss(db_session):
    halted = await evaluate_daily_loss_halts(
        db_session, now=_NOW, account_ids=[], paper_user_ids=[]
    )
    assert halted == set()


def test_compose_halt_flags_matches_prefix():
    uid = uuid4()
    flags = compose_halt_flags(
        position_ref=f"paper:{uid}:nba-2025-01-15-lal-bos:yes",
        price_feed_stale=False,
        daily_loss_refs={f"paper:{uid}"},
    )
    assert flags.daily_loss_halt is True
    assert flags.price_feed_stale is False


def test_global_kill_via_settings(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("HEARTBEAT_GLOBAL_KILL", "true")
    get_settings.cache_clear()
    try:
        flags = compose_halt_flags(
            position_ref="clob:x:m:yes",
            price_feed_stale=False,
            daily_loss_refs=set(),
        )
        assert flags.global_kill is True
        pos = PositionSnapshot(
            position_ref="clob:x:m:yes",
            entry_price=Decimal("0.50"),
            mark_price=Decimal("0.50"),
            opened_at=_NOW - timedelta(seconds=10),
            price_as_of=_NOW - timedelta(seconds=1),
            quantity=Decimal("1"),
        )
        d = decide(pos, _RULES, now=_NOW, halts=flags)
        assert d.action is HeartbeatAction.EMERGENCY
        assert d.rule_fired == "global_kill"
    finally:
        monkeypatch.delenv("HEARTBEAT_GLOBAL_KILL", raising=False)
        get_settings.cache_clear()


def test_pod_registry_absent_is_none():
    from app.services.heartbeat_halts import _try_pod_daily_pnl

    assert _try_pod_daily_pnl("any-pod") is None
