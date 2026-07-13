import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.core.event_bus import get_event_bus
from app.db.models import (
    Account,
    DomainEvent,
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
from app.services.paper_account_service import PaperAccountService


@pytest.mark.asyncio
async def test_cancel_endpoint_returns_403_for_other_owner_and_409_for_filled(db_session):
    market = await MarketService(db_session).create_market(
        slug="cancel-status-semantics",
        title="Cancellation status semantics",
        question="Will cancellation return precise status codes?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    token = "22222222-2222-4222-8222-222222222222"
    actor_id = PaperAccountService.session_account_id(token)
    actor = Account(id=actor_id, name="Cancellation actor", cash_balance=Decimal("100"))
    owner = Account(name="Cancellation owner", cash_balance=Decimal("100"))
    db_session.add_all([actor, owner])
    await db_session.flush()
    other_owner_order = Order(
        market_id=market.id,
        account_id=owner.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome.YES,
        order_type=OrderType.LIMIT,
        price=Decimal("0.55"),
        quantity=Decimal("10"),
        status=OrderStatus.OPEN,
    )
    filled_order = Order(
        market_id=market.id,
        account_id=actor.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome.YES,
        order_type=OrderType.LIMIT,
        price=Decimal("0.55"),
        quantity=Decimal("10"),
        filled_quantity=Decimal("10"),
        status=OrderStatus.FILLED,
    )
    db_session.add_all([other_owner_order, filled_order])
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            headers = {"X-Paper-Account-Token": token}
            forbidden = await client.post(
                f"/api/v1/orders/{other_owner_order.id}/cancel",
                headers=headers,
                json={"account_id": str(actor.id)},
            )
            conflict = await client.post(
                f"/api/v1/orders/{filled_order.id}/cancel",
                headers=headers,
                json={"account_id": str(actor.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Order does not belong to account"
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Filled orders cannot be cancelled"


@pytest.mark.asyncio
async def test_concurrent_cancel_releases_reservation_and_emits_once(tmp_path):
    database_path = (tmp_path / "concurrent-cancel.sqlite3").as_posix()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        connect_args={"timeout": 30},
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with factory() as setup_session:
            market = Market(
                slug="concurrent-cancel",
                title="Concurrent cancellation",
                question="Will reserved funds release exactly once?",
            )
            account = Account(name="Concurrent canceller", cash_balance=Decimal("100"))
            setup_session.add_all([market, account])
            await setup_session.flush()
            order = Order(
                market_id=market.id,
                account_id=account.id,
                side=OrderSide.BUY,
                outcome=OrderOutcome.YES,
                order_type=OrderType.LIMIT,
                price=Decimal("0.55"),
                quantity=Decimal("10"),
                status=OrderStatus.OPEN,
            )
            setup_session.add(order)
            await setup_session.commit()
            order_id = order.id
            account_id = account.id

        async with factory() as before_session:
            assert await OrderBookService(before_session).reserved_cash(account_id) == Decimal(
                "5.5000"
            )

        async def cancel_once() -> OrderStatus:
            async with factory() as session:
                cancelled = await OrderBookService(session).cancel_order(order_id, account_id)
                await session.commit()
                return cancelled.status

        bus_subscription = get_event_bus().subscribe("order.cancelled")
        try:
            statuses = await asyncio.gather(cancel_once(), cancel_once())
            public_event = await asyncio.wait_for(bus_subscription.get(), timeout=2)
        finally:
            bus_subscription.close()
        assert statuses == [OrderStatus.CANCELLED, OrderStatus.CANCELLED]

        async with factory() as verification_session:
            order_status = await verification_session.scalar(
                select(Order.status).where(Order.id == order_id)
            )
            event_count = await verification_session.scalar(
                select(func.count())
                .select_from(DomainEvent)
                .where(DomainEvent.event_type == "order_cancelled")
            )
            reserved = await OrderBookService(verification_session).reserved_cash(account_id)

        assert order_status == OrderStatus.CANCELLED
        assert event_count == 1
        assert reserved == Decimal("0")
        assert public_event["order_id"] == str(order_id)
        assert public_event["status"] == "cancelled"
        assert "account_id" not in public_event
        assert "side" not in public_event
        assert "outcome" not in public_event
    finally:
        await engine.dispose()
