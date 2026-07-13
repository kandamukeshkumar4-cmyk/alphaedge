from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Account,
    DomainEvent,
    JobRun,
    Market,
    Order,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService
from app.workers.order_expiry import (
    ORDER_EXPIRY_JOB_NAME,
    order_expiry_task,
    sweep_expired_orders,
)
from app.workers.tasks import WorkerSettings


def _order_payload(account_id: UUID, expires_at: datetime) -> dict:
    return {
        "account_id": str(account_id),
        "side": "buy",
        "outcome": "yes",
        "order_type": "limit",
        "quantity": "10",
        "price": "0.55",
        "expires_at": expires_at.isoformat(),
        "risk": {
            "predicted_prob": 0.62,
            "confidence": 0.8,
            "edge": 0.07,
            "current_drawdown": 0,
            "minutes_before_start": 120,
        },
    }


@pytest.mark.asyncio
async def test_gtd_order_api_persists_future_expiry_and_rejects_past(db_session):
    market = await MarketService(db_session).create_market(
        slug="gtd-order-api",
        title="GTD order API",
        question="Will the expiry contract be enforced?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
    )
    account = await MarketService(db_session).seed_system_account(
        UUID("00000000-0000-0000-0000-000000000001"),
        Decimal("100000"),
        "System Paper Account",
    )
    future = datetime.now(UTC) + timedelta(hours=1)
    past = datetime.now(UTC) - timedelta(minutes=1)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            accepted = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                json=_order_payload(account.id, future),
            )
            rejected = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                json=_order_payload(account.id, past),
            )
    finally:
        app.dependency_overrides.clear()

    assert accepted.status_code == 200
    assert datetime.fromisoformat(accepted.json()["expires_at"]) == future
    assert rejected.status_code == 400
    assert "order expiry must be in the future" in rejected.json()["detail"]


@pytest.mark.asyncio
async def test_expiry_sweep_cancels_expired_leaves_future_and_is_idempotent(db_session):
    now = datetime.now(UTC)
    market = Market(
        slug="gtd-sweep",
        title="GTD sweep",
        question="Will only expired orders be cancelled?",
    )
    account = Account(name="GTD account", cash_balance=Decimal("100"))
    db_session.add_all([market, account])
    await db_session.flush()
    expired = Order(
        market_id=market.id,
        account_id=account.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome.YES,
        order_type=OrderType.LIMIT,
        price=Decimal("0.55"),
        quantity=Decimal("10"),
        status=OrderStatus.OPEN,
        expires_at=now - timedelta(seconds=1),
    )
    future = Order(
        market_id=market.id,
        account_id=account.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome.NO,
        order_type=OrderType.LIMIT,
        price=Decimal("0.60"),
        quantity=Decimal("10"),
        status=OrderStatus.OPEN,
        expires_at=now + timedelta(hours=1),
    )
    db_session.add_all([expired, future])
    await db_session.flush()

    first = await sweep_expired_orders(db_session, now=now, limit=10)
    second = await sweep_expired_orders(db_session, now=now, limit=10)
    await db_session.refresh(expired)
    await db_session.refresh(future)
    event_count = await db_session.scalar(
        select(func.count())
        .select_from(DomainEvent)
        .where(DomainEvent.event_type == "order_cancelled")
    )
    reserved = await OrderBookService(db_session).reserved_cash(account.id)

    assert first == {"scanned": 1, "expired": 1, "skipped": 0}
    assert second == {"scanned": 0, "expired": 0, "skipped": 0}
    assert expired.status == OrderStatus.CANCELLED
    assert future.status == OrderStatus.OPEN
    assert event_count == 1
    assert reserved == Decimal("6.0000")


@pytest.mark.asyncio
async def test_order_expiry_task_records_job_run(tmp_path):
    now = datetime.now(UTC)
    database_path = (tmp_path / "order-expiry-task.sqlite3").as_posix()
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as setup_session:
            market = Market(
                slug="gtd-task",
                title="GTD task",
                question="Will the task record its heartbeat?",
            )
            account = Account(name="GTD task account", cash_balance=Decimal("100"))
            setup_session.add_all([market, account])
            await setup_session.flush()
            setup_session.add(
                Order(
                    market_id=market.id,
                    account_id=account.id,
                    side=OrderSide.BUY,
                    outcome=OrderOutcome.YES,
                    order_type=OrderType.LIMIT,
                    price=Decimal("0.55"),
                    quantity=Decimal("10"),
                    status=OrderStatus.OPEN,
                    expires_at=now - timedelta(seconds=1),
                )
            )
            await setup_session.commit()

        summary = await order_expiry_task(
            {"session_factory": factory, "now": now, "limit": 10}
        )

        async with factory() as verification_session:
            run = await verification_session.scalar(
                select(JobRun).where(JobRun.job_name == ORDER_EXPIRY_JOB_NAME)
            )
            status_value = await verification_session.scalar(select(Order.status))

        assert summary == {"scanned": 1, "expired": 1, "skipped": 0}
        assert run is not None
        assert run.status == "success"
        assert run.summary == summary
        assert status_value == OrderStatus.CANCELLED
    finally:
        await engine.dispose()


def test_order_expiry_task_is_registered_with_minute_cron():
    assert order_expiry_task in WorkerSettings.functions
    cron_function_names = {
        getattr(getattr(job, "coroutine", None), "__name__", "")
        for job in WorkerSettings.cron_jobs
    }
    assert "order_expiry_task" in cron_function_names
