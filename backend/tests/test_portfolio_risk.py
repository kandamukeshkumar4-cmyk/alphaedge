"""Portfolio risk metrics (E12): pure math + authenticated endpoint."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import MarketResolution, PaperOrder
from app.db.session import get_db
from app.main import app
from app.services.portfolio_risk import (
    ClosedTrade,
    OpenExposure,
    compute_risk_metrics,
    max_drawdown,
    per_trade_sharpe,
)

# ── pure math ────────────────────────────────────────────────────────────────


def test_max_drawdown_simple_dip():
    # +10, -4, -3 (trough at 3), +5 → peak 10, trough 3 → drawdown 7
    assert max_drawdown([10, -4, -3, 5]) == 7.0


def test_max_drawdown_no_losses_is_zero():
    assert max_drawdown([1, 2, 3]) == 0.0
    assert max_drawdown([]) == 0.0


def test_max_drawdown_all_losses_measures_from_zero_peak():
    assert max_drawdown([-5, -5]) == 10.0


def test_per_trade_sharpe_needs_two_trades_and_variance():
    assert per_trade_sharpe([ClosedTrade(cost=10, realized_pnl=1)]) is None
    flat = [ClosedTrade(cost=10, realized_pnl=1)] * 3
    assert per_trade_sharpe(flat) is None  # zero variance → no meaningful score


def test_per_trade_sharpe_known_value():
    # returns: 0.2 and -0.1 → mean 0.05, sample std = 0.2121…, sharpe ≈ 0.2357
    trades = [ClosedTrade(cost=10, realized_pnl=2), ClosedTrade(cost=10, realized_pnl=-1)]
    assert per_trade_sharpe(trades) == pytest.approx(0.2357, abs=1e-3)


def test_compute_risk_metrics_aggregates():
    closed = [
        ClosedTrade(cost=10, realized_pnl=5),
        ClosedTrade(cost=10, realized_pnl=-2),
        ClosedTrade(cost=20, realized_pnl=1),
    ]
    open_exp = [
        OpenExposure(category="Sports", cost=30),
        OpenExposure(category="Sports", cost=10),
        OpenExposure(category="Politics", cost=60),
    ]
    m = compute_risk_metrics(closed, open_exp)
    assert m.n_closed == 3
    assert m.total_realized_pnl == 4.0
    assert m.win_rate == pytest.approx(2 / 3, abs=1e-4)
    assert m.max_drawdown == 2.0
    assert m.exposure_by_category == {"Sports": 40.0, "Politics": 60.0}
    assert m.exposure_pct_by_category == {"Sports": 40.0, "Politics": 60.0}


def test_compute_risk_metrics_empty_book():
    m = compute_risk_metrics([], [])
    assert m.n_closed == 0
    assert m.win_rate is None
    assert m.sharpe is None
    assert m.max_drawdown == 0.0
    assert m.exposure_by_category == {}


# ── endpoint ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_token(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


@pytest.mark.asyncio
async def test_portfolio_risk_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/portfolio/risk")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_risk_empty_book(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, _ = await _signup_token(client, "risk-empty@example.com")
        response = await client.get(
            "/api/v1/portfolio/risk", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["n_closed"] == 0
    assert body["win_rate"] is None
    assert body["paper_trading_only"] is True
    assert "Paper trading only" in body["disclaimer"]


@pytest.mark.asyncio
async def test_portfolio_risk_with_settled_trades(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await _signup_token(client, "risk-trades@example.com")
        # Two settled positions with REAL settlement semantics: the portfolio
        # query derives settlement PnL from market_resolutions (win pays
        # shares - cost, loss pays -cost), so seed resolutions, not realized_pnl.
        db_session.add(
            PaperOrder(
                id=uuid4(), user_id=UUID(user_id), slug="risk-m1", side="yes",
                outcome="yes", shares=Decimal("10"), price=Decimal("0.5"),
                cost=Decimal("5"), action="BUY", settled=True,
            )
        )
        db_session.add(
            PaperOrder(
                id=uuid4(), user_id=UUID(user_id), slug="risk-m2", side="yes",
                outcome="yes", shares=Decimal("10"), price=Decimal("0.4"),
                cost=Decimal("4"), action="BUY", settled=True,
            )
        )
        db_session.add(MarketResolution(id=uuid4(), slug="risk-m1", outcome="YES"))
        db_session.add(MarketResolution(id=uuid4(), slug="risk-m2", outcome="NO"))
        await db_session.flush()
        response = await client.get(
            "/api/v1/portfolio/risk", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["n_closed"] == 2
    assert body["win_rate"] == pytest.approx(0.5)
    assert body["total_realized_pnl"] == pytest.approx(1.0)
    assert body["max_drawdown"] == pytest.approx(4.0)
