import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Account, DomainEvent, Order, OrderOutcome, OrderSide, OrderType
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService


def _order_payload(account_id: UUID) -> dict:
    return {
        "account_id": str(account_id),
        "side": "buy",
        "outcome": "yes",
        "order_type": "limit",
        "quantity": "10",
        "price": "0.55",
        "risk": {
            "predicted_prob": 0.62,
            "confidence": 0.8,
            "edge": 0.07,
            "current_drawdown": 0,
            "minutes_before_start": 120,
        },
    }


@pytest.mark.asyncio
async def test_clob_idempotency_header_replays_original_ack(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="clob-idempotency-replay",
        title="CLOB idempotency replay",
        question="Will a retried request create only one order?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account = await market_service.seed_system_account(
        UUID("00000000-0000-0000-0000-000000000001"),
        Decimal("100000"),
        "System Paper Account",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            headers = {"Idempotency-Key": "clob-retry-1"}
            first = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers,
                json=_order_payload(account.id),
            )
            second = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers,
                json=_order_payload(account.id),
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    orders = (
        await db_session.scalars(
            select(Order).where(
                Order.account_id == account.id,
                Order.idempotency_key == "clob-retry-1",
            )
        )
    ).all()
    assert len(orders) == 1
    book = await OrderBookService(db_session).get_l2(market.id)
    assert book["yes"]["bids"] == [{"price": 0.55, "size": 10.0}]


@pytest.mark.asyncio
async def test_concurrent_clob_duplicate_submissions_create_one_order(tmp_path):
    database_path = (tmp_path / "clob-idempotency.sqlite3").as_posix()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        connect_args={"timeout": 30},
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with factory() as setup_session:
            market = await MarketService(setup_session).create_market(
                slug="clob-idempotency-concurrent",
                title="Concurrent CLOB idempotency",
                question="Will concurrent retries produce one order?",
                lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
            )
            account = Account(name="Concurrent Buyer", cash_balance=Decimal("1000"))
            setup_session.add(account)
            await setup_session.commit()
            market_id = market.id
            account_id = account.id

        async def submit_duplicate() -> UUID:
            async with factory() as session:
                order = await OrderBookService(session).submit_order(
                    market_id,
                    account_id,
                    OrderSide.BUY,
                    OrderOutcome.YES,
                    OrderType.LIMIT,
                    Decimal("10"),
                    Decimal("0.55"),
                    idempotency_key="clob-concurrent-1",
                )
                await session.commit()
                return order.id

        order_ids = await asyncio.gather(submit_duplicate(), submit_duplicate())
        assert order_ids[0] == order_ids[1]

        async with factory() as verification_session:
            order_count = await verification_session.scalar(
                select(func.count())
                .select_from(Order)
                .where(
                    Order.account_id == account_id,
                    Order.idempotency_key == "clob-concurrent-1",
                )
            )
            event_count = await verification_session.scalar(
                select(func.count())
                .select_from(DomainEvent)
                .where(DomainEvent.event_type == "order_submitted")
            )
            assert order_count == 1
            assert event_count == 1
            book = await OrderBookService(verification_session).get_l2(market_id)
            assert book["yes"]["bids"] == [{"price": 0.55, "size": 10.0}]
    finally:
        await engine.dispose()
