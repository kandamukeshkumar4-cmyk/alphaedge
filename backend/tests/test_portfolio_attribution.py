"""B2 — performance attribution math + API (avoids E12 double-count)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import MarketResolution, PaperOrder, User
from app.db.session import get_db
from app.main import app
from app.services.analytics_attribution import (
    OrderLeg,
    attributed_trades,
    compute_attribution,
)
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def _leg(**kwargs) -> OrderLeg:
    defaults = dict(
        id=str(uuid4()),
        slug="m1",
        outcome="YES",
        action="BUY",
        shares=10.0,
        cost=4.0,
        realized_pnl=None,
        settled=True,
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
        category="Sports",
        title="M1",
    )
    defaults.update(kwargs)
    return OrderLeg(**defaults)


def test_attribution_settlement_only_no_sell_double_count():
    """BUY settled via resolve: one SETTLE leg; no phantom SUM(realized_pnl)."""
    buy = _leg(id="buy1", realized_pnl=None, shares=10, cost=4)
    trades = attributed_trades([buy], {"m1": "YES"})
    assert len(trades) == 1
    assert trades[0].side == "SETTLE"
    assert trades[0].realized_pnl == pytest.approx(6.0)  # 10 - 4
    report = compute_attribution(trades)
    assert report.roi == pytest.approx(1.5)
    assert report.win_rate == pytest.approx(1.0)


def test_attribution_sell_plus_remaining_settlement_disjoint():
    """Partial SELL then resolve remaining — SELL pnl XOR settlement, not both."""
    buy = _leg(id="buy1", shares=10, cost=5.0, action="BUY")
    sell = _leg(
        id="sell1",
        shares=4,
        cost=2.4,
        action="SELL",
        realized_pnl=0.4,  # sold above avg
        created_at=datetime(2026, 1, 16, tzinfo=UTC),
    )
    trades = attributed_trades([buy, sell], {"m1": "YES"})
    sides = {t.side for t in trades}
    assert sides == {"SELL", "SETTLE"}
    sell_leg = next(t for t in trades if t.side == "SELL")
    settle_leg = next(t for t in trades if t.side == "SETTLE")
    assert sell_leg.realized_pnl == pytest.approx(0.4)
    # remaining 6 shares, cost basis 5 * 6/10 = 3 → pnl 6 - 3 = 3
    assert settle_leg.cost == pytest.approx(3.0)
    assert settle_leg.realized_pnl == pytest.approx(3.0)
    # Total 3.4 — NOT 0.4 + (10-5) which would be the E12-style overcount
    report = compute_attribution(trades)
    assert report.total_realized_pnl == pytest.approx(3.4)


def test_attribution_monthly_and_category_and_top_bottom():
    t1 = _leg(
        id="a",
        slug="a",
        cost=10,
        shares=10,
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
        category="Sports",
    )
    t2 = _leg(
        id="b",
        slug="b",
        cost=10,
        shares=10,
        created_at=datetime(2026, 2, 10, tzinfo=UTC),
        category="Politics",
        outcome="NO",
    )
    trades = attributed_trades(
        [t1, t2],
        {"a": "YES", "b": "YES"},  # t2 loses
    )
    report = compute_attribution(trades, top_n=1)
    assert report.top_trades[0].slug == "a"
    assert report.bottom_trades[0].slug == "b"
    assert report.monthly_pnl["2026-01"] == pytest.approx(0.0)
    assert report.monthly_pnl["2026-02"] == pytest.approx(-10.0)
    # t1 win: 10-10=0; t2 loss: -10
    assert report.category_pnl["Politics"] == pytest.approx(-10.0)
    assert report.win_rate == pytest.approx(0.0)  # wins require pnl > 0
    assert report.n_trades == 2


def test_attribution_empty():
    report = compute_attribution([])
    assert report.win_rate is None
    assert report.n_trades == 0
    assert report.roi == 0.0


async def _signup(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert r.status_code == 201
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_attribution_endpoint_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/portfolio/attribution")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_attribution_endpoint_empty_book(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "attr-empty@example.com")
        r = await client.get(
            "/api/v1/portfolio/attribution",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["n_trades"] == 0
    assert body["top_trades"] == []
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_attribution_endpoint_after_resolve(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "attr-winner@example.com")
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.4},
        )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        r = await client.get(
            "/api/v1/portfolio/attribution",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["n_trades"] == 1
    assert body["total_realized_pnl"] == pytest.approx(6.0)
    assert body["roi"] == pytest.approx(1.5)
    assert body["win_rate"] == pytest.approx(1.0)
    assert body["top_trades"][0]["slug"] == CANONICAL_SLUG
    assert "Sports" in body["category_pnl"] or body["category_pnl"]


@pytest.mark.asyncio
async def test_attribution_no_double_count_with_sell_leg(db_session):
    """Seed BUY+SELL settled rows; total must not include E12 double-count."""
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "attr-partial@example.com")
        # Create user via signup; pull user id from JWT path by placing orders
        buy = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
        assert buy.status_code in (200, 201)

    # Insert a SELL leg + mark both settled with a resolution (bypass close API sizing)
    user = (
        await db_session.execute(select(User).where(User.email == "attr-partial@example.com"))
    ).scalar_one()
    sell = PaperOrder(
        user_id=user.id,
        slug=CANONICAL_SLUG,
        side="YES",
        outcome="yes",
        shares=Decimal("4"),
        price=Decimal("0.6"),
        cost=Decimal("2.4"),
        action="SELL",
        realized_pnl=Decimal("0.4"),
        settled=True,
    )
    db_session.add(sell)
    buys = (
        await db_session.execute(
            select(PaperOrder).where(
                PaperOrder.user_id == user.id, PaperOrder.action == "BUY"
            )
        )
    ).scalars().all()
    for b in buys:
        b.settled = True
    if not (
        await db_session.execute(
            select(MarketResolution).where(MarketResolution.slug == CANONICAL_SLUG)
        )
    ).scalar_one_or_none():
        db_session.add(MarketResolution(slug=CANONICAL_SLUG, outcome="YES"))
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/portfolio/attribution",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    # SELL 0.4 + SETTLE remaining 6 @ cost 3 → 3.0 = 3.4 total (not 0.4+5)
    assert body["total_realized_pnl"] == pytest.approx(3.4)
    assert body["n_trades"] == 2
