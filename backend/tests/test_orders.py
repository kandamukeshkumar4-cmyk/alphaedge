from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import OddsSnapshot, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


async def _signup_token(client: AsyncClient, email: str = "orders@example.com") -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_place_order_requires_auth(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/orders",
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_place_order_rejects_invalid_slug(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client)
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": "not-in-catalog", "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid market slug"


@pytest.mark.asyncio
async def test_place_order_rejects_non_positive_shares(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "shares@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 0, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_place_order_rejects_price_out_of_range(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "price@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 1.0},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_place_order_rejects_insufficient_balance(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "balance@example.com")
        await MarketService(db_session).seed_catalog_markets()
        user = await db_session.scalar(
            select(User).where(User.email == "balance@example.com")
        )
        user.paper_balance = Decimal("1")
        await db_session.flush()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient paper balance"


@pytest.mark.asyncio
async def test_place_order_accepts_valid_order_and_deducts_balance(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "valid@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "NO", "shares": 20, "price": 0.4},
        )
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == CANONICAL_SLUG
    assert body["side"] == "NO"
    assert body["shares"] == 20
    assert body["cost"] == 8.0
    assert body["remaining_balance"] == 99_992.0
    assert body["paper_trading_only"] is True
    assert body["order_id"]

    assert me.status_code == 200
    assert me.json()["paper_balance"] == 99_992.0


@pytest.mark.asyncio
async def test_place_order_idempotency_key_replays_first_order(db_session):
    """Audit C-RACE-01/H-RACE-01: a retried POST with the same Idempotency-Key
    must return the original order and debit the balance exactly once."""
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "idem@example.com")
        await MarketService(db_session).seed_catalog_markets()
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "retry-abc-123",
        }
        payload = {"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5}
        first = await client.post("/api/v1/orders", headers=headers, json=payload)
        second = await client.post("/api/v1/orders", headers=headers, json=payload)
        me = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    app.dependency_overrides.clear()

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["order_id"] == first.json()["order_id"]
    assert me.json()["paper_balance"] == 99_995.0  # debited once, not twice


@pytest.mark.asyncio
async def test_place_order_rejects_price_far_from_market(db_session):
    """Audit H-RACE-02: client price must sit near the latest authoritative
    snapshot — no self-dealing at fantasy prices."""
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "offmarket@example.com")
        await MarketService(db_session).seed_catalog_markets()
        db_session.add(
            OddsSnapshot(
                market_slug=CANONICAL_SLUG,
                implied_yes=Decimal("0.50"),
                source="polymarket.gamma",
                captured_at=datetime.now(timezone.utc),
            )
        )
        await db_session.flush()
        headers = {"Authorization": f"Bearer {token}"}
        lowball = await client.post(
            "/api/v1/orders",
            headers=headers,
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.05},
        )
        fair = await client.post(
            "/api/v1/orders",
            headers=headers,
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.45},
        )
    app.dependency_overrides.clear()

    assert lowball.status_code == 409
    assert fair.status_code == 201


@pytest.mark.asyncio
async def test_place_order_rejects_locked_market(db_session):
    """Audit M-SEC-04 / C-SEC-01: the paper buy path must refuse a market that
    is no longer open, matching the CLOB path's tradability guard."""
    from app.db.models import Market, MarketStatus

    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "locked@example.com")
        await MarketService(db_session).seed_catalog_markets()
        market = await db_session.scalar(select(Market).where(Market.slug == CANONICAL_SLUG))
        market.status = MarketStatus.LOCKED
        await db_session.flush()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "not open" in response.json()["detail"]


@pytest.mark.asyncio
async def test_place_order_rejects_market_past_lock_at(db_session):
    """Audit M-SEC-04: a market past its lock_at is closed for new orders even
    while nominally OPEN."""
    from app.db.models import Market

    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "pastlock@example.com")
        await MarketService(db_session).seed_catalog_markets()
        market = await db_session.scalar(select(Market).where(Market.slug == CANONICAL_SLUG))
        market.lock_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        await db_session.flush()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "locked" in response.json()["detail"].lower()
