from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    Account,
    LedgerEntry,
    Order,
    OrderOutcome,
    OrderSide,
    OrderType,
)
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService


@pytest.mark.asyncio
async def test_order_api_rejects_low_edge_before_creating_order(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-risk-gated-market",
        title="Risk gated NBA market",
        question="Will the risk gate reject weak edge?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account = Account(name="Risk Test Trader", cash_balance=Decimal("10000"))
    db_session.add(account)
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                json={
                    "account_id": str(account.id),
                    "side": "buy",
                    "outcome": "yes",
                    "order_type": "limit",
                    "quantity": "10",
                    "price": "0.55",
                    "risk": {
                        "predicted_prob": 0.56,
                        "confidence": 0.8,
                        "edge": 0.01,
                        "current_drawdown": 0,
                        "minutes_before_start": 120,
                    },
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "edge" in response.json()["detail"]
    orders = (await db_session.execute(select(Order))).scalars().all()
    assert orders == []


@pytest.mark.asyncio
async def test_order_api_accepts_risk_approved_paper_order(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-risk-approved-market",
        title="Risk approved NBA market",
        question="Will the risk gate approve strong edge?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account = Account(name="Risk Approved Trader", cash_balance=Decimal("10000"))
    db_session.add(account)
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                json={
                    "account_id": str(account.id),
                    "side": "buy",
                    "outcome": "yes",
                    "order_type": "limit",
                    "quantity": "10",
                    "price": "0.55",
                    "risk": {
                        "predicted_prob": 0.62,
                        "confidence": 0.8,
                        "edge": 0.07,
                        "current_drawdown": 0.02,
                        "minutes_before_start": 120,
                    },
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == str(account.id)
    assert payload["market_id"] == str(market.id)
    assert payload["status"] == "open"


@pytest.mark.asyncio
async def test_paper_account_endpoint_seeds_and_returns_account_once(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first = await client.get("/api/v1/paper-account")
            second = await client.get("/api/v1/paper-account")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload == second.json()
    assert payload["paper_trading_only"] is True
    assert payload["name"] == "System Paper Account"
    assert payload["cash_balance"] == "100000.0000"
    assert payload["positions"] == []

    ledger_entries = (await db_session.execute(select(LedgerEntry))).scalars().all()
    assert len(ledger_entries) == 1


@pytest.mark.asyncio
async def test_paper_account_reports_open_orders_and_reserved_cash(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-account-open-order-market",
        title="Account open order market",
        question="Will account state expose open orders?",
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
            order_response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                json={
                    "account_id": str(account.id),
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
                },
            )
            account_response = await client.get("/api/v1/paper-account")
    finally:
        app.dependency_overrides.clear()

    assert order_response.status_code == 200
    assert account_response.status_code == 200
    payload = account_response.json()
    assert payload["cash_balance"] == "100000.0000"
    assert payload["reserved_cash"] == "5.5000"
    assert payload["available_cash"] == "99994.5000"
    assert payload["open_orders"] == [
        {
            "id": order_response.json()["id"],
            "market_id": str(market.id),
            "market_slug": "nba-account-open-order-market",
            "market_title": "Account open order market",
            "side": "buy",
            "outcome": "yes",
            "order_type": "limit",
            "price": "0.5500",
            "quantity": "10.0000",
            "filled_quantity": "0.0000",
            "remaining_quantity": "10.0000",
            "reserved_notional": "5.5000",
            "status": "open",
        }
    ]


@pytest.mark.asyncio
async def test_order_book_rejects_buy_when_open_orders_reserve_cash(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-reserved-cash-market",
        title="Reserved cash market",
        question="Will open buy orders reserve cash?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account = Account(name="Reserve Test Trader", cash_balance=Decimal("100"))
    db_session.add(account)
    await db_session.flush()

    order_book = OrderBookService(db_session)
    await order_book.submit_order(
        market.id,
        account.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("100"),
        Decimal("0.90"),
    )

    with pytest.raises(ValueError, match="Insufficient available cash"):
        await order_book.submit_order(
            market.id,
            account.id,
            OrderSide.BUY,
            OrderOutcome.YES,
            OrderType.LIMIT,
            Decimal("20"),
            Decimal("0.60"),
        )
