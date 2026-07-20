"""Tests for live portfolio mark-to-market P&L (Loop R)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Market, MarketStatus, OddsSnapshot
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_unsettled_position_has_unrealized_pnl(db_session):
    await MarketService(db_session).seed_catalog_markets()
    db_session.add(
        OddsSnapshot(
            market_slug=CANONICAL_SLUG,
            implied_yes=Decimal("0.70"),
            source="test",
            captured_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "live-pnl@example.com")
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            # 0.65 sits inside the ±0.10 tolerance band around the live 0.70
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.65},
        )
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    pos = body["positions"][0]
    assert pos["settled"] is False
    assert pos["current_price"] == pytest.approx(0.70, abs=0.001)
    assert pos["unrealized_pnl"] == pytest.approx(0.5, abs=0.01)


@pytest.mark.asyncio
async def test_portfolio_value_includes_mark_to_market(db_session):
    await MarketService(db_session).seed_catalog_markets()
    db_session.add(
        OddsSnapshot(
            market_slug=CANONICAL_SLUG,
            implied_yes=Decimal("0.60"),
            source="test",
            captured_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "portfolio-value@example.com")
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 20, "price": 0.5},
        )
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    # balance 100000 - 10 cost + 20*0.60 mark = 100002
    assert body["portfolio_value"] == pytest.approx(100002.0, abs=0.05)


@pytest.mark.asyncio
async def test_settled_position_has_zero_unrealized_pnl(db_session):
    from app.core.config import get_settings

    await MarketService(db_session).seed_catalog_markets()
    admin_headers = {"X-Admin-API-Key": get_settings().admin_api_key}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "settled-pnl@example.com")
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 5, "price": 0.5},
        )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=admin_headers,
            json={"winning_outcome": "YES"},
        )
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )

    pos = response.json()["positions"][0]
    assert pos["settled"] is True
    assert pos["unrealized_pnl"] == 0.0


@pytest.mark.asyncio
async def test_locked_unsettled_position_discloses_no_terminal_pnl(db_session):
    await MarketService(db_session).seed_catalog_markets()
    market = await db_session.scalar(select(Market).where(Market.slug == CANONICAL_SLUG))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "locked-unsettled@example.com")
        order = await client.post(
            "/api/v1/orders", headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 5, "price": 0.5},
        )
        assert order.status_code == 201
        market.status = MarketStatus.LOCKED
        response = await client.get("/api/v1/portfolio", headers={"Authorization": f"Bearer {token}"})

    position = response.json()["positions"][0]
    assert position["settlement_status"] == "locked_unsettled"
    assert position["settled"] is False
    assert position["unrealized_pnl"] == 0.0
