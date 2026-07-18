"""Loop V59 H2 — heartbeat manager loop registration + detail + flag skip."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.observability import loop_state
from app.observability.loop_state import LOOP_INTERVALS
from app.services.heartbeat_decision import HaltFlags, PositionSnapshot
from app.db.models import Account, Market, Order, OrderOutcome, OrderSide, OrderStatus, OrderType, Position
from app.services.heartbeat_manager import (
    _TrackedPosition,
    _load_clob_positions,
    heartbeat_exit_idempotency_key,
    heartbeat_detail,
    heartbeat_manager_task,
    run_heartbeat_pass,
)


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    loop_state.reset()
    yield
    app.dependency_overrides.clear()
    loop_state.reset()


def test_heartbeat_interval_registered():
    assert LOOP_INTERVALS["heartbeat_manager"] == 45


def test_heartbeat_detail_counts():
    detail = heartbeat_detail(
        {
            "scanned": 3,
            "hold": 2,
            "tighten": 0,
            "exit": 1,
            "emergency": 0,
            "logged": 3,
            "exits_submitted": 0,
            "errors": 0,
        }
    )
    assert detail is not None
    assert "scanned=3" in detail
    assert "exit=1" in detail
    assert "logged=3" in detail


@pytest.mark.asyncio
async def test_heartbeat_task_skips_when_flag_off(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("HEARTBEAT_MANAGER_ENABLED", "false")
    get_settings.cache_clear()
    try:
        result = await heartbeat_manager_task({})
        assert result["skipped"] is True
        assert "HEARTBEAT_MANAGER_ENABLED" in result["reason"]
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_system_loops_includes_heartbeat_manager():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")
    assert response.status_code == 200
    by_name = {row["name"]: row for row in response.json()["loops"]}
    assert "heartbeat_manager" in by_name
    assert by_name["heartbeat_manager"]["interval_sec"] == 45
    assert by_name["heartbeat_manager"]["status"] == "never"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "halts",
    [
        HaltFlags(global_kill=True),
        HaltFlags(price_feed_stale=True),
        HaltFlags(daily_loss_halt=True),
    ],
)
async def test_global_halts_log_without_submitting_a_clob_exit(db_session, monkeypatch, halts):
    now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
    tracked = _TrackedPosition(
        snapshot=PositionSnapshot(
            position_ref="clob:test:market:yes",
            entry_price=Decimal("0.50"),
            mark_price=Decimal("0.60"),
            opened_at=now - timedelta(minutes=5),
            price_as_of=now - timedelta(seconds=1),
            quantity=Decimal("2"),
            source="clob",
        ),
        account_id=uuid4(),
        market_id=uuid4(),
        market_slug="market",
    )

    async def load_paper(_session):
        return []

    async def load_clob(_session):
        return [tracked]

    async def forbidden_submit(*_args, **_kwargs):
        raise AssertionError("halted heartbeat must not submit a CLOB exit")

    monkeypatch.setattr("app.services.heartbeat_manager._load_paper_positions", load_paper)
    monkeypatch.setattr("app.services.heartbeat_manager._load_clob_positions", load_clob)
    monkeypatch.setattr("app.services.heartbeat_manager._submit_clob_exit", forbidden_submit)

    summary = await run_heartbeat_pass(db_session, now=now, halts=halts)

    assert summary["exits_submitted"] == 0
    assert summary["emergency"] == 1


def test_heartbeat_exit_idempotency_key_is_position_unique_and_utc_daily():
    same_day = datetime(2026, 7, 17, 23, 30, tzinfo=timezone.utc)
    next_day = datetime(2026, 7, 18, 0, 1, tzinfo=timezone.utc)
    first = heartbeat_exit_idempotency_key("clob:account:market:yes", same_day)

    assert first == heartbeat_exit_idempotency_key("clob:account:market:yes", same_day)
    assert first != heartbeat_exit_idempotency_key("clob:other:market:yes", same_day)
    assert first.endswith("-20260717")
    assert heartbeat_exit_idempotency_key("clob:account:market:yes", next_day).endswith("-20260718")


@pytest.mark.asyncio
async def test_clob_opened_at_comes_from_earliest_related_order_not_position_update(db_session):
    now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
    account = Account(name="heartbeat account", cash_balance=Decimal("100"))
    market = Market(slug="heartbeat-opened-at", title="t", question="q")
    db_session.add_all([account, market])
    await db_session.flush()
    position = Position(
        account_id=account.id,
        market_id=market.id,
        yes_shares=Decimal("2"),
        avg_yes_cost=Decimal("0.50"),
        updated_at=now - timedelta(minutes=1),
    )
    old_order = Order(
        account_id=account.id,
        market_id=market.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome.YES,
        order_type=OrderType.MARKET,
        quantity=Decimal("2"),
        filled_quantity=Decimal("2"),
        status=OrderStatus.FILLED,
        created_at=now - timedelta(hours=2),
    )
    db_session.add_all([position, old_order])
    await db_session.commit()

    tracked = await _load_clob_positions(db_session)

    assert tracked[0].snapshot.opened_at == old_order.created_at.replace(tzinfo=None)
    assert tracked[0].snapshot.opened_at != position.updated_at.replace(tzinfo=None)
