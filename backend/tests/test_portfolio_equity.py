"""B5 — portfolio equity snapshots + equity-curve API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import PortfolioEquitySnapshot, User
from app.db.session import get_db
from app.main import app
from app.services.analytics_equity import snapshot_user_equity
from app.workers.portfolio_equity import EQUITY_SNAPSHOT_JOB_NAME, portfolio_equity_snapshot_task
from app.workers.tasks import WorkerSettings


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
async def test_snapshot_idempotent_per_day(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "eq-idem@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "eq-idem@example.com"))
    ).scalar_one()
    day = date(2026, 7, 13)
    first = await snapshot_user_equity(db_session, user, snapshot_date=day)
    second = await snapshot_user_equity(db_session, user, snapshot_date=day)
    await db_session.commit()
    assert first is not None
    assert second is None
    rows = (
        await db_session.scalars(
            select(PortfolioEquitySnapshot).where(
                PortfolioEquitySnapshot.user_id == user.id
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].equity == Decimal(str(user.paper_balance))


@pytest.mark.asyncio
async def test_equity_curve_ordered(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "eq-curve@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "eq-curve@example.com"))
    ).scalar_one()
    for d, cash in (
        (date(2026, 7, 10), "100"),
        (date(2026, 7, 12), "110"),
        (date(2026, 7, 11), "105"),
    ):
        user.paper_balance = Decimal(cash)
        await snapshot_user_equity(db_session, user, snapshot_date=d)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/portfolio/equity-curve",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    points = r.json()["points"]
    assert [p["date"] for p in points] == ["2026-07-10", "2026-07-11", "2026-07-12"]
    assert points[0]["equity"] == pytest.approx(100.0)
    assert points[-1]["equity"] == pytest.approx(110.0)


@pytest.mark.asyncio
async def test_equity_curve_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/portfolio/equity-curve")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_snapshot_task_heartbeat(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "eq-task@example.com")

    class _Ctx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc):
            return False

    def factory():
        return _Ctx()

    summary = await portfolio_equity_snapshot_task(
        {"session_factory": factory, "snapshot_date": date(2026, 7, 13)}
    )
    assert summary["created"] >= 1
    assert summary["date"] == "2026-07-13"


def test_worker_registered():
    assert portfolio_equity_snapshot_task in WorkerSettings.functions
    assert EQUITY_SNAPSHOT_JOB_NAME == "portfolio_equity_snapshot_task"
