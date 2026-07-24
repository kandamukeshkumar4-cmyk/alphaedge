"""Loop V92 P1 — portfolio analytics service tests (paper only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import MarketResolution, PaperOrder, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.portfolio_analytics_service import compute_portfolio_analytics

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert r.status_code == 201
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_analytics_empty_portfolio_zeros(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "analytics-empty@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "analytics-empty@example.com"))
    ).scalar_one()
    result = await compute_portfolio_analytics(db_session, user, days=30)
    assert result["pnl_series"] == []
    assert result["summary"]["total_realized"] == 0.0
    assert result["summary"]["total_unrealized"] == 0.0
    assert result["summary"]["win_rate"] == 0.0
    assert result["summary"]["trades_closed"] == 0
    assert result["summary"]["trades_open"] == 0
    assert result["summary"]["best_trade"] == 0.0
    assert result["summary"]["worst_trade"] == 0.0
    assert result["summary"]["avg_hold_hours"] == 0.0
    assert result["calibration"]["buckets"] == []
    assert result["calibration"]["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_analytics_win_rate_and_pnl_math(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "analytics-win@example.com")
        buy = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.4},
        )
        assert buy.status_code in (200, 201)
        resolve = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        assert resolve.status_code == 200

    user = (
        await db_session.execute(select(User).where(User.email == "analytics-win@example.com"))
    ).scalar_one()
    await db_session.refresh(user)
    result = await compute_portfolio_analytics(db_session, user, days=7)
    summary = result["summary"]
    assert summary["trades_closed"] == 1
    assert summary["trades_open"] == 0
    assert summary["win_rate"] == pytest.approx(1.0)
    assert summary["total_realized"] == pytest.approx(6.0)
    assert summary["best_trade"] == pytest.approx(6.0)
    assert summary["worst_trade"] == pytest.approx(6.0)
    assert summary["total_unrealized"] == pytest.approx(0.0)
    assert len(result["pnl_series"]) == 7
    assert result["pnl_series"][-1]["realized_pnl"] == pytest.approx(6.0)
    assert result["pnl_series"][-1]["unrealized_pnl"] == pytest.approx(0.0)
    assert set(result["pnl_series"][0]) == {"date", "realized_pnl", "unrealized_pnl", "equity"}


@pytest.mark.asyncio
async def test_analytics_mixed_win_loss_and_open(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "analytics-mixed@example.com")
        r1 = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
        assert r1.status_code in (200, 201)
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "NO"},
        )

    user = (
        await db_session.execute(select(User).where(User.email == "analytics-mixed@example.com"))
    ).scalar_one()
    await db_session.refresh(user)

    win_slug = "analytics-win-market"
    open_slug = "analytics-open-market"
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PaperOrder(
                user_id=user.id,
                slug=win_slug,
                side="YES",
                outcome="yes",
                shares=Decimal("10"),
                price=Decimal("0.3"),
                cost=Decimal("3.0"),
                action="BUY",
                settled=True,
                created_at=now - timedelta(hours=5),
            ),
            PaperOrder(
                user_id=user.id,
                slug=open_slug,
                side="YES",
                outcome="yes",
                shares=Decimal("4"),
                price=Decimal("0.5"),
                cost=Decimal("2.0"),
                action="BUY",
                settled=False,
                created_at=now,
            ),
        ]
    )
    db_session.add(MarketResolution(slug=win_slug, outcome="YES"))
    await db_session.flush()

    result = await compute_portfolio_analytics(db_session, user, days=3)
    summary = result["summary"]
    assert summary["trades_closed"] == 2
    assert summary["win_rate"] == pytest.approx(0.5)
    assert summary["total_realized"] == pytest.approx(2.0)
    assert summary["best_trade"] == pytest.approx(7.0)
    assert summary["worst_trade"] == pytest.approx(-5.0)
    assert summary["trades_open"] == 1
    assert summary["avg_hold_hours"] >= 0.0


@pytest.mark.asyncio
async def test_analytics_calibration_empty_without_closed_probs(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "analytics-cal-empty@example.com")
    user = (
        await db_session.execute(
            select(User).where(User.email == "analytics-cal-empty@example.com")
        )
    ).scalar_one()
    result = await compute_portfolio_analytics(db_session, user, days=30)
    assert result["calibration"]["buckets"] == []
    assert result["calibration"]["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_analytics_calibration_decile_buckets(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "analytics-cal@example.com")
        # Entry implied 0.4 in decile 0.4-0.5; resolve YES => win
        buy = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.4},
        )
        assert buy.status_code in (200, 201)
        resolve = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        assert resolve.status_code == 200

    user = (
        await db_session.execute(select(User).where(User.email == "analytics-cal@example.com"))
    ).scalar_one()
    await db_session.refresh(user)
    result = await compute_portfolio_analytics(db_session, user, days=30)
    buckets = result["calibration"]["buckets"]
    assert result["calibration"]["paper_trading_only"] is True
    assert len(buckets) >= 1
    matched = [b for b in buckets if b["predicted_prob_bucket"] == "0.4-0.5"]
    assert len(matched) == 1
    assert matched[0]["n"] == 1
    assert matched[0]["actual_rate"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_analytics_calibration_mixed_bucket_rate(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "analytics-cal-mix@example.com")
    user = (
        await db_session.execute(
            select(User).where(User.email == "analytics-cal-mix@example.com")
        )
    ).scalar_one()
    now = datetime.now(UTC)
    # Two settled buys at 0.65: one win, one loss => actual_rate 0.5 in 0.6-0.7
    db_session.add_all(
        [
            PaperOrder(
                user_id=user.id,
                slug="cal-m1",
                side="YES",
                outcome="yes",
                shares=Decimal("10"),
                price=Decimal("0.65"),
                cost=Decimal("6.5"),
                action="BUY",
                settled=True,
                created_at=now,
            ),
            PaperOrder(
                user_id=user.id,
                slug="cal-m2",
                side="YES",
                outcome="yes",
                shares=Decimal("10"),
                price=Decimal("0.65"),
                cost=Decimal("6.5"),
                action="BUY",
                settled=True,
                created_at=now,
            ),
            MarketResolution(slug="cal-m1", outcome="YES"),
            MarketResolution(slug="cal-m2", outcome="NO"),
        ]
    )
    await db_session.flush()
    result = await compute_portfolio_analytics(db_session, user, days=14)
    matched = [
        b for b in result["calibration"]["buckets"]
        if b["predicted_prob_bucket"] == "0.6-0.7"
    ]
    assert len(matched) == 1
    assert matched[0]["n"] == 2
    assert matched[0]["actual_rate"] == pytest.approx(0.5)

