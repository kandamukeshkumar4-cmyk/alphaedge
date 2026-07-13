from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    Account,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.db.session import get_db
from app.main import app
from app.schemas.market import OrderFillBreakdownResponse, OrderHistoryItemResponse
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService
from app.services.paper_account_service import PaperAccountService


def test_clob_order_history_normalizes_aware_timestamps_to_utc():
    source_timestamp = datetime(
        2026,
        7,
        13,
        12,
        0,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )
    fill = OrderFillBreakdownResponse(
        id=uuid4(),
        price=Decimal("0.5555"),
        quantity=Decimal("0.1000"),
        created_at=source_timestamp,
    )
    item = OrderHistoryItemResponse(
        id=uuid4(),
        market_id=uuid4(),
        market_slug="utc-history",
        market_title="UTC history",
        side=OrderSide.BUY,
        outcome=OrderOutcome.YES,
        order_type=OrderType.LIMIT,
        price=Decimal("0.5555"),
        quantity=Decimal("0.2000"),
        filled_quantity=Decimal("0.1000"),
        remaining_quantity=Decimal("0.1000"),
        filled_notional=Decimal("0.0556"),
        average_fill_price=Decimal("0.5555"),
        status=OrderStatus.PARTIAL,
        expires_at=source_timestamp,
        created_at=source_timestamp,
        fills=[fill],
    )

    payload = item.model_dump(mode="json")

    assert payload["created_at"] == "2026-07-13T06:30:00+00:00"
    assert payload["expires_at"] == "2026-07-13T06:30:00+00:00"
    assert payload["fills"][0]["created_at"] == "2026-07-13T06:30:00+00:00"


@pytest.mark.asyncio
async def test_clob_order_history_is_authenticated_filtered_and_cursor_paginated(
    db_session,
):
    first_market = await MarketService(db_session).create_market(
        slug="clob-history-first",
        title="CLOB history first",
        question="Will the first history market settle?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
    )
    second_market = await MarketService(db_session).create_market(
        slug="clob-history-second",
        title="CLOB history second",
        question="Will the second history market settle?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
    )
    token = str(uuid4())
    account_id = PaperAccountService.session_account_id(token)
    buyer = Account(id=account_id, name="History buyer", cash_balance=Decimal("100"))
    seller = Account(name="History seller", cash_balance=Decimal("100"))
    db_session.add_all([buyer, seller])
    await db_session.flush()

    service = OrderBookService(db_session)
    await service.submit_order(
        first_market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("0.1"),
        Decimal("0.5555"),
    )
    partial = await service.submit_order(
        first_market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("0.2"),
        Decimal("0.5555"),
    )
    open_order = await service.submit_order(
        second_market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.NO,
        OrderType.LIMIT,
        Decimal("2"),
        Decimal("0.40"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    cancelled = await service.submit_order(
        second_market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("3"),
        Decimal("0.30"),
    )
    await service.cancel_order(cancelled.id, buyer.id)
    same_second = datetime.now(UTC).replace(microsecond=0)
    partial.created_at = same_second + timedelta(microseconds=123_100)
    open_order.created_at = same_second + timedelta(microseconds=123_900)
    cancelled.created_at = same_second + timedelta(microseconds=123_500)
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    headers = {"X-Paper-Account-Token": token}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            unauthenticated = await client.get(
                "/api/v1/orders",
                params={"account_id": str(account_id)},
            )
            wrong_owner = await client.get(
                "/api/v1/orders",
                params={"account_id": str(account_id)},
                headers={"X-Paper-Account-Token": str(uuid4())},
            )
            partial_page = await client.get(
                "/api/v1/orders",
                params={
                    "account_id": str(account_id),
                    "status": "partial",
                    "market": first_market.slug,
                },
                headers=headers,
            )
            cancelled_page = await client.get(
                "/api/v1/orders",
                params={
                    "account_id": str(account_id),
                    "status": "cancelled",
                    "market": second_market.slug,
                },
                headers=headers,
            )
            first_page = await client.get(
                "/api/v1/orders",
                params={"account_id": str(account_id), "limit": 2},
                headers=headers,
            )
            first_payload = first_page.json()
            second_page = await client.get(
                "/api/v1/orders",
                params={
                    "account_id": str(account_id),
                    "limit": 2,
                    "cursor": first_payload["next_cursor"],
                },
                headers=headers,
            )
            invalid_cursor = await client.get(
                "/api/v1/orders",
                params={"account_id": str(account_id), "cursor": "not-a-cursor!"},
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert unauthenticated.status_code == 401
    assert wrong_owner.status_code == 400
    assert partial_page.status_code == 200
    partial_payload = partial_page.json()
    assert partial_payload["next_cursor"] is None
    assert len(partial_payload["items"]) == 1
    partial_item = partial_payload["items"][0]
    assert partial_item["id"] == str(partial.id)
    assert partial_item["status"] == "partial"
    assert partial_item["filled_quantity"] == "0.1000"
    assert partial_item["remaining_quantity"] == "0.1000"
    assert partial_item["filled_notional"] == "0.0556"
    assert partial_item["average_fill_price"] == "0.5555"
    assert datetime.fromisoformat(partial_item["created_at"]).tzinfo is not None
    assert len(partial_item["fills"]) == 1
    assert partial_item["fills"][0]["price"] == "0.5555"
    assert partial_item["fills"][0]["quantity"] == "0.1000"
    assert datetime.fromisoformat(partial_item["fills"][0]["created_at"]).tzinfo is not None

    assert cancelled_page.status_code == 200
    assert [item["id"] for item in cancelled_page.json()["items"]] == [
        str(cancelled.id)
    ]

    assert first_page.status_code == 200
    assert first_payload["next_cursor"]
    assert second_page.status_code == 200
    second_payload = second_page.json()
    all_ids = [item["id"] for item in first_payload["items"] + second_payload["items"]]
    assert len(all_ids) == 3
    assert len(set(all_ids)) == 3
    assert set(all_ids) == {str(partial.id), str(open_order.id), str(cancelled.id)}
    assert second_payload["next_cursor"] is None
    assert invalid_cursor.status_code == 400
    assert invalid_cursor.json()["detail"] == "Invalid order history cursor"
