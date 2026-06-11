from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    Account,
    Fill,
    LedgerEntry,
    Order,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
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
    headers = {"X-Paper-Account-Token": "11111111-1111-4111-8111-000000000001"}

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            account = await client.get("/api/v1/paper-account", headers=headers)
            response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers,
                json={
                    "account_id": account.json()["id"],
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
    headers = {"X-Paper-Account-Token": "11111111-1111-4111-8111-000000000002"}

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            account = await client.get("/api/v1/paper-account", headers=headers)
            response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers,
                json={
                    "account_id": account.json()["id"],
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
    assert payload["account_id"] == account.json()["id"]
    assert payload["market_id"] == str(market.id)
    assert payload["status"] == "open"


@pytest.mark.asyncio
async def test_order_api_derives_start_window_from_market_lock_at(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-stale-lock-risk-market",
        title="Stale lock risk market",
        question="Will stale markets ignore client risk timing?",
        lock_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    headers = {"X-Paper-Account-Token": "11111111-1111-4111-8111-000000000003"}

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            account = await client.get("/api/v1/paper-account", headers=headers)
            response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers,
                json={
                    "account_id": account.json()["id"],
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
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "too close to game start" in response.json()["detail"]
    orders = (await db_session.execute(select(Order))).scalars().all()
    assert orders == []


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
async def test_paper_account_token_creates_isolated_public_session_accounts(db_session):
    async def override_get_db():
        yield db_session

    headers_a = {"X-Paper-Account-Token": "11111111-1111-4111-8111-111111111111"}
    headers_b = {"X-Paper-Account-Token": "22222222-2222-4222-8222-222222222222"}

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first_a = await client.get("/api/v1/paper-account", headers=headers_a)
            second_a = await client.get("/api/v1/paper-account", headers=headers_a)
            first_b = await client.get("/api/v1/paper-account", headers=headers_b)
    finally:
        app.dependency_overrides.clear()

    assert first_a.status_code == 200
    assert second_a.status_code == 200
    assert first_b.status_code == 200
    assert first_a.json() == second_a.json()
    assert first_a.json()["id"] != first_b.json()["id"]
    assert first_a.json()["name"] == "Paper Session Account"
    assert first_b.json()["name"] == "Paper Session Account"
    assert first_a.json()["cash_balance"] == "100000.0000"
    assert first_b.json()["cash_balance"] == "100000.0000"

    ledger_entries = (await db_session.execute(select(LedgerEntry))).scalars().all()
    assert len(ledger_entries) == 2


@pytest.mark.asyncio
async def test_paper_order_token_rejects_cross_session_account_replay(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-session-replay-market",
        title="Session replay market",
        question="Will account tokens bind public paper orders?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    headers_a = {"X-Paper-Account-Token": "11111111-1111-4111-8111-111111111111"}
    headers_b = {"X-Paper-Account-Token": "22222222-2222-4222-8222-222222222222"}

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            account_a = await client.get("/api/v1/paper-account", headers=headers_a)
            account_b = await client.get("/api/v1/paper-account", headers=headers_b)
            replay_response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers_b,
                json={
                    "account_id": account_a.json()["id"],
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
            valid_response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                headers=headers_a,
                json={
                    "account_id": account_a.json()["id"],
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
            account_a_after = await client.get("/api/v1/paper-account", headers=headers_a)
            account_b_after = await client.get("/api/v1/paper-account", headers=headers_b)
    finally:
        app.dependency_overrides.clear()

    assert account_a.status_code == 200
    assert account_b.status_code == 200
    assert replay_response.status_code == 400
    assert "account token does not match account_id" in replay_response.json()["detail"]
    assert valid_response.status_code == 200
    assert valid_response.json()["account_id"] == account_a.json()["id"]
    assert account_a_after.json()["reserved_cash"] == "5.5000"
    assert account_a_after.json()["open_orders"][0]["id"] == valid_response.json()["id"]
    assert account_b_after.json()["id"] == account_b.json()["id"]
    assert account_b_after.json()["reserved_cash"] == "0.0000"
    assert account_b_after.json()["open_orders"] == []


@pytest.mark.asyncio
async def test_session_account_positions_require_matching_token(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-position-token-market",
        title="Position token market",
        question="Will positions be token scoped?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    headers_a = {"X-Paper-Account-Token": "11111111-1111-4111-8111-111111111111"}
    headers_b = {"X-Paper-Account-Token": "22222222-2222-4222-8222-222222222222"}

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            account_a = await client.get("/api/v1/paper-account", headers=headers_a)
            account_b = await client.get("/api/v1/paper-account", headers=headers_b)
            db_session.add(
                Position(
                    account_id=UUID(account_a.json()["id"]),
                    market_id=market.id,
                    yes_shares=Decimal("3"),
                )
            )
            await db_session.flush()

            missing = await client.get(f"/api/v1/accounts/{account_a.json()['id']}/positions")
            replay = await client.get(
                f"/api/v1/accounts/{account_a.json()['id']}/positions",
                headers=headers_b,
            )
            valid = await client.get(
                f"/api/v1/accounts/{account_a.json()['id']}/positions",
                headers=headers_a,
            )
    finally:
        app.dependency_overrides.clear()

    assert account_a.status_code == 200
    assert account_b.status_code == 200
    assert missing.status_code == 401
    assert replay.status_code == 400
    assert valid.status_code == 200
    assert valid.json() == [
        {
            "market_id": str(market.id),
            "yes_shares": "3.0000",
            "no_shares": "0.0000",
            "avg_yes_cost": "0.0000",
            "avg_no_cost": "0.0000",
        }
    ]


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


@pytest.mark.asyncio
async def test_order_cancel_releases_reserved_cash_and_removes_open_order_from_account(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-cancel-reserved-cash-market",
        title="Cancel reserved cash market",
        question="Will cancellation release reserved paper cash?",
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
            before_cancel = await client.get("/api/v1/paper-account")
            cancel_response = await client.post(
                f"/api/v1/orders/{order_response.json()['id']}/cancel",
                json={"account_id": str(account.id)},
            )
            after_cancel = await client.get("/api/v1/paper-account")
    finally:
        app.dependency_overrides.clear()

    assert order_response.status_code == 200
    assert before_cancel.status_code == 200
    assert before_cancel.json()["reserved_cash"] == "5.5000"
    assert len(before_cancel.json()["open_orders"]) == 1
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    payload = after_cancel.json()
    assert payload["reserved_cash"] == "0.0000"
    assert payload["available_cash"] == "100000.0000"
    assert payload["open_orders"] == []

    order = await db_session.get(Order, UUID(order_response.json()["id"]))
    assert order is not None
    assert order.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_admin_smoke_account_keeps_deploy_orders_out_of_public_portfolio(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-smoke-account-isolation-market",
        title="Smoke account isolation market",
        question="Will smoke tests stay out of the public paper account?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            public_before = await client.get("/api/v1/paper-account")
            smoke_account = await client.get(
                "/admin/smoke-account",
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
            order_response = await client.post(
                f"/api/v1/markets/{market.slug}/orders",
                json={
                    "account_id": smoke_account.json()["id"],
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
            public_after_order = await client.get("/api/v1/paper-account")
            smoke_after_order = await client.get(
                "/admin/smoke-account",
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
            cancel_response = await client.post(
                f"/api/v1/orders/{order_response.json()['id']}/cancel",
                json={"account_id": smoke_account.json()["id"]},
            )
            public_after_cancel = await client.get("/api/v1/paper-account")
    finally:
        app.dependency_overrides.clear()

    assert public_before.status_code == 200
    assert smoke_account.status_code == 200
    assert smoke_account.json()["name"] == "Deployment Smoke Account"
    assert order_response.status_code == 200
    assert order_response.json()["account_id"] == smoke_account.json()["id"]
    assert public_after_order.status_code == 200
    assert public_after_order.json()["reserved_cash"] == "0.0000"
    assert public_after_order.json()["open_orders"] == []
    assert public_after_order.json()["order_history"] == []
    assert smoke_after_order.status_code == 200
    assert smoke_after_order.json()["reserved_cash"] == "5.5000"
    assert [order["id"] for order in smoke_after_order.json()["open_orders"]] == [
        order_response.json()["id"]
    ]
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    assert public_after_cancel.status_code == 200
    assert public_after_cancel.json()["reserved_cash"] == "0.0000"
    assert public_after_cancel.json()["open_orders"] == []
    assert public_after_cancel.json()["order_history"] == []


@pytest.mark.asyncio
async def test_paper_account_reports_closed_order_history_for_partial_market_fill(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-account-order-history-market",
        title="Account order history market",
        question="Will closed order history expose partial market fills?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    seller = Account(name="History Liquidity Seller", cash_balance=Decimal("22.50"))
    db_session.add(seller)
    account = await market_service.seed_system_account(
        UUID("00000000-0000-0000-0000-000000000001"),
        Decimal("100000"),
        "System Paper Account",
    )
    await db_session.flush()

    order_book = OrderBookService(db_session)
    await order_book.submit_order(
        market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("50"),
        Decimal("0.55"),
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
                    "order_type": "market",
                    "quantity": "100",
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
    assert order_response.json()["status"] == "cancelled"
    assert Decimal(order_response.json()["filled_quantity"]) == Decimal("50")

    payload = account_response.json()
    assert payload["open_orders"] == []
    assert payload["order_history"] == [
        {
            "id": order_response.json()["id"],
            "market_id": str(market.id),
            "market_slug": "nba-account-order-history-market",
            "market_title": "Account order history market",
            "side": "buy",
            "outcome": "yes",
            "order_type": "market",
            "price": "0.5500",
            "quantity": "100.0000",
            "filled_quantity": "50.0000",
            "remaining_quantity": "50.0000",
            "filled_notional": "27.5000",
            "average_fill_price": "0.5500",
            "status": "cancelled",
            "created_at": payload["order_history"][0]["created_at"],
        }
    ]


@pytest.mark.asyncio
async def test_cancelled_order_is_removed_from_in_memory_book_before_matching(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-cancel-book-market",
        title="Cancel book market",
        question="Will cancelled orders stop matching?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    buyer = Account(name="Cancel Buyer", cash_balance=Decimal("100"))
    seller = Account(name="Cancel Seller", cash_balance=Decimal("100"))
    db_session.add_all([buyer, seller])
    await db_session.flush()

    order_book = OrderBookService(db_session)
    buy_order = await order_book.submit_order(
        market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.70"),
    )

    cancelled_order = await order_book.cancel_order(buy_order.id, buyer.id)
    assert cancelled_order.status == OrderStatus.CANCELLED

    sell_order = await order_book.submit_order(
        market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.60"),
    )

    fills = (await db_session.execute(select(Fill))).scalars().all()
    assert fills == []
    assert sell_order.status == OrderStatus.OPEN
