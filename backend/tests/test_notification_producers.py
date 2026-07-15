"""Loop V24 N2 — notification producers (never raise into producer txn)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Notification, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.notification_producers import (
    mirror_alert_to_admin_notifications,
    notify_order_cancelled,
    notify_order_filled,
    social_follow_tables_present,
)
from app.services.notification_service import create_notification_best_effort

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_paper_order_creates_notification(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/v1/auth/signup",
            json={"email": "n2-fill@example.com", "password": "securepass1"},
        )
        token = r.json()["access_token"]
        await MarketService(db_session).seed_catalog_markets()
        place = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 5,
                "price": 0.5,
            },
        )
        assert place.status_code in (200, 201), place.text

        listed = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert listed.status_code == 200
    body = listed.json()
    assert body["unread_count"] >= 1
    assert any(i["type"] == "order_filled" for i in body["items"])
    assert any(CANONICAL_SLUG in i["body"] for i in body["items"])


@pytest.mark.asyncio
async def test_notify_order_filled_never_raises(db_session):
    # Invalid session-less path with nonsense still must not raise.
    await notify_order_filled(
        user_id=uuid4(),
        order_id="deadbeef-0000-0000-0000-000000000001",
        slug="x",
        side="YES",
        outcome="yes",
        shares=1.0,
        price=0.5,
        session=db_session,
    )
    # With a real user it persists.
    user = User(
        email="n2-direct@example.com",
        hashed_password="x",
    )
    db_session.add(user)
    await db_session.flush()
    await notify_order_filled(
        user_id=user.id,
        order_id=str(uuid4()),
        slug="nba-2025-01-15-lal-bos",
        side="YES",
        outcome="yes",
        shares=2.0,
        price=0.4,
        session=db_session,
    )
    await db_session.commit()
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user_id == user.id)
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].type == "order_filled"


@pytest.mark.asyncio
async def test_notify_cancelled_skips_without_user():
    # Must not raise when user_id is unknown.
    await notify_order_cancelled(
        user_id=None,
        order_id=str(uuid4()),
        market_id=str(uuid4()),
        remaining_quantity="3",
    )


@pytest.mark.asyncio
async def test_social_follow_tables_present_detects_follows():
    """Mapped social model uses ``follows`` (SEC-Z2-01 / Loop V27 X1)."""
    assert social_follow_tables_present() is True


@pytest.mark.asyncio
async def test_best_effort_swallows_errors(db_session, monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "app.services.notification_service.create_notification", boom
    )
    result = await create_notification_best_effort(
        user_id=uuid4(),
        type="order_filled",
        title="t",
        body="b",
        session=db_session,
    )
    assert result is None


@pytest.mark.asyncio
async def test_admin_mirror_ops_alert(db_session, monkeypatch):
    user = User(email="admin-n2@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "notification_admin_emails", "admin-n2@example.com")

    # Mirror uses AsyncSessionLocal — point it at the test engine.
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    import app.db.session as session_mod

    factory = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", factory)

    n = await mirror_alert_to_admin_notifications(
        alert_type="ops_error_rate",
        message="HTTP 5xx elevated",
        payload={},
    )
    assert n == 1
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user_id == user.id)
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].type == "ops_error_rate"


@pytest.mark.asyncio
async def test_admin_mirror_skips_non_ops():
    n = await mirror_alert_to_admin_notifications(
        alert_type="alignment",
        message="not ops",
        payload={},
    )
    assert n == 0


@pytest.mark.asyncio
async def test_admin_mirror_calibration_and_forecast_drift(db_session, monkeypatch):
    """Real drift dispatch types are calibration_drift / forecast_drift (not drift_*)."""
    user = User(email="admin-drift@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    from app.core.config import get_settings
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    import app.db.session as session_mod

    settings = get_settings()
    monkeypatch.setattr(settings, "notification_admin_emails", "admin-drift@example.com")
    factory = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", factory)

    n1 = await mirror_alert_to_admin_notifications(
        alert_type="calibration_drift",
        message="ECE elevated",
        payload={},
    )
    n2 = await mirror_alert_to_admin_notifications(
        alert_type="forecast_drift",
        message="Brier elevated",
        payload={},
    )
    assert n1 == 1
    assert n2 == 1
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user_id == user.id)
        )
    ).all()
    types = {r.type for r in rows}
    assert "calibration_drift" in types
    assert "forecast_drift" in types
