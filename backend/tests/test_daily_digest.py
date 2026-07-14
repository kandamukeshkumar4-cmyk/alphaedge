"""Loop V24 N3 — daily digest worker (idempotent per user per day)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Notification, User
from app.db.session import get_db
from app.main import app
from app.workers.daily_digest import (
    DAILY_DIGEST_JOB_NAME,
    build_digest_for_user,
    daily_digest_task,
    run_daily_digest,
)
from app.workers.tasks import WorkerSettings


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_digest_idempotent_per_user_per_day(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "digest-idem@example.com", "password": "securepass1"},
        )
    user = (
        await db_session.execute(
            select(User).where(User.email == "digest-idem@example.com")
        )
    ).scalar_one()
    day = date(2026, 7, 14)
    first = await build_digest_for_user(db_session, user, day=day)
    second = await build_digest_for_user(db_session, user, day=day)
    await db_session.commit()
    assert first is not None
    assert first.type == "digest"
    assert "Daily digest" in first.title
    assert second is None
    rows = (
        await db_session.scalars(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.type == "digest",
            )
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_digest_summarizes_cash(db_session):
    user = User(
        email="digest-cash@example.com",
        hashed_password="x",
        paper_balance=Decimal("12345.50"),
    )
    db_session.add(user)
    await db_session.flush()
    row = await build_digest_for_user(db_session, user, day=date(2026, 7, 14))
    await db_session.commit()
    assert row is not None
    assert "12345.50" in row.body
    assert "Watchlist empty" in row.body or "watchlist" in row.body.lower()


@pytest.mark.asyncio
async def test_run_daily_digest_batch(db_session):
    for i in range(2):
        db_session.add(
            User(
                email=f"digest-batch-{i}@example.com",
                hashed_password="x",
            )
        )
    await db_session.flush()
    day = date(2026, 7, 14)
    summary = await run_daily_digest(db_session, day=day)
    await db_session.commit()
    assert summary["created"] >= 2
    # Second pass skips everyone already digested.
    summary2 = await run_daily_digest(db_session, day=day)
    await db_session.commit()
    assert summary2["created"] == 0
    assert summary2["skipped"] >= 2


@pytest.mark.asyncio
async def test_daily_digest_task_jobrun(db_session):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    db_session.add(User(email="digest-task@example.com", hashed_password="x"))
    await db_session.commit()

    summary = await daily_digest_task(
        {"session_factory": factory, "digest_date": date(2026, 7, 14)}
    )
    assert summary["created"] >= 1
    assert summary["date"] == "2026-07-14"

    from app.db.models import JobRun

    jobs = (
        await db_session.scalars(
            select(JobRun).where(JobRun.job_name == DAILY_DIGEST_JOB_NAME)
        )
    ).all()
    assert len(jobs) >= 1
    assert jobs[-1].status == "success"


def test_daily_digest_registered_on_worker():
    assert daily_digest_task in WorkerSettings.functions
    # arq cron wraps the function; check name presence on cron entries.
    names = []
    for c in WorkerSettings.cron_jobs:
        fn = getattr(c, "coroutine", None) or getattr(c, "func", None) or c
        names.append(getattr(fn, "__name__", str(fn)))
    assert "daily_digest_task" in names


def test_main_loop_symbol_exists():
    from app import main as main_mod

    assert hasattr(main_mod, "_daily_digest_loop")
    assert callable(main_mod._daily_digest_loop)
