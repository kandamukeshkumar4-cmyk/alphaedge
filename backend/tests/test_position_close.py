import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import MarketResolution, PaperOrder, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": get_settings().admin_api_key}


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


async def _signup_token(client: AsyncClient, email: str = "close@example.com") -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


async def _buy_yes(
    client: AsyncClient,
    token: str,
    shares: float = 10,
    price: float = 0.4,
) -> None:
    response = await client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"slug": CANONICAL_SLUG, "side": "YES", "shares": shares, "price": price},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_close_requires_auth(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/positions/close",
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 5, "price": 0.5},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_close_rejects_invalid_slug(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "invalid-slug@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": "not-in-catalog", "outcome": "yes", "shares": 5, "price": 0.5},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid market slug"


@pytest.mark.asyncio
async def test_close_rejects_when_no_position(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "no-position@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 5, "price": 0.5},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot sell more shares than held"


@pytest.mark.asyncio
async def test_close_full_position_credits_balance_and_realizes_pnl(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "full-close@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token, shares=10, price=0.4)
        response = await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 10, "price": 0.6},
        )
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["proceeds"] == 6.0
    assert body["realized_pnl"] == 2.0
    assert body["remaining_shares"] == 0.0
    assert body["remaining_balance"] == 100_002.0
    assert me.json()["paper_balance"] == 100_002.0


@pytest.mark.asyncio
async def test_partial_close_leaves_remainder(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "partial@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token, shares=10, price=0.4)
        first = await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 4, "price": 0.5},
        )
        second = await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 7, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert first.status_code == 200
    assert first.json()["remaining_shares"] == 6.0
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_close_rejects_resolved_market(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "resolved@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token)
        db_session.add(MarketResolution(slug=CANONICAL_SLUG, outcome="YES"))
        await db_session.flush()
        response = await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 10, "price": 0.6},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_close_writes_sell_order_row(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "sell-row@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token)
        await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 10, "price": 0.6},
        )
        history = await client.get(
            "/api/v1/orders/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        sell_rows = (
            await db_session.scalars(select(PaperOrder).where(PaperOrder.action == "SELL"))
        ).all()
    app.dependency_overrides.clear()

    assert len(sell_rows) == 1
    assert sell_rows[0].realized_pnl is not None
    assert any(item["action"] == "SELL" for item in history.json())


@pytest.mark.asyncio
async def test_portfolio_nets_out_sold_shares(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "portfolio-net@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token, shares=10, price=0.4)
        await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 4, "price": 0.5},
        )
        portfolio = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    body = portfolio.json()
    position = next(p for p in body["positions"] if p["market_slug"] == CANONICAL_SLUG)
    assert position["shares"] == 6.0
    assert position["avg_cost"] == 0.4
    assert position["realized_pnl"] == pytest.approx(0.4)
    assert body["realized_pnl"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_rebuy_after_partial_close_nets_into_one_weighted_position(db_session):
    """O02 regression: buy -> partial sell -> re-buy must collapse to a SINGLE
    net position keyed by (slug, side, outcome), with a BUY-weighted average
    cost — not one row per order, and not reset by the intervening sell.

    Sequence: buy 10 @ 0.40 (cost 4.0); sell 4 @ 0.50 (realized +0.40);
    buy 10 @ 0.60 (cost 6.0). Net = 16 shares; weighted avg over both BUYs =
    (4.0 + 6.0) / (10 + 10) = 0.50; remaining cost basis 16 * 0.50 = 8.0;
    realized P&L from the partial sell (0.40) is preserved."""
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "rebuy-net@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token, shares=10, price=0.4)
        await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 4, "price": 0.5},
        )
        await _buy_yes(client, token, shares=10, price=0.6)
        portfolio = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    body = portfolio.json()
    matches = [p for p in body["positions"] if p["market_slug"] == CANONICAL_SLUG]
    assert len(matches) == 1, "re-buy after partial close must not split into multiple rows"
    position = matches[0]
    assert position["shares"] == pytest.approx(16.0)
    assert position["avg_cost"] == pytest.approx(0.5)
    assert position["cost"] == pytest.approx(8.0)
    assert position["realized_pnl"] == pytest.approx(0.4)
    assert position["settled"] is False


@pytest.mark.asyncio
async def test_fully_closed_position_not_double_paid_on_settlement(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "no-double@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token, shares=10, price=0.4)
        await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 10, "price": 0.6},
        )
        user = await db_session.scalar(select(User).where(User.email == "no-double@example.com"))
        balance_after_close = user.paper_balance

        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        await db_session.refresh(user)
        portfolio = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    assert user.paper_balance == balance_after_close
    position = next(p for p in portfolio.json()["positions"] if p["market_slug"] == CANONICAL_SLUG)
    assert position["shares"] == 0.0
    assert position["settled"] is True


@pytest.mark.asyncio
async def test_partial_sell_then_resolve_portfolio_consistent(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "partial-resolve@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token, shares=10, price=0.4)
        await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 4, "price": 0.5},
        )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        user = await db_session.scalar(select(User).where(User.email == "partial-resolve@example.com"))
        await db_session.refresh(user)
        portfolio = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    # start 100000, buy -4.0 = 99996, sell +2.0 = 99998, settle 6 shares +6.0 = 100004
    assert user.paper_balance == pytest.approx(100004.0)
    position = next(p for p in portfolio.json()["positions"] if p["market_slug"] == CANONICAL_SLUG)
    # realized_pnl: sell gain = 4*(0.5-0.4)=0.4, settlement = 6*(1.0-0.4)=3.6, total = 4.0
    assert position["realized_pnl"] == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_portfolio_summary_excludes_closed_positions(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "summary@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await _buy_yes(client, token)
        await client.post(
            "/api/v1/positions/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 10, "price": 0.6},
        )
        summary = await client.get(
            "/api/v1/portfolio/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert summary.json()["open_positions"] == 0
