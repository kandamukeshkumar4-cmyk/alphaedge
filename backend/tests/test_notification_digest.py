"""Loop V90 N4 — email notification digest task tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Notification, NotificationPreference, SignalEvent, User
from app.services.notification_digest_service import compose_digest_body
from app.services.notification_service import create_notification
from app.workers.tasks import send_notification_digest_task


def _smtp_on(**extra):
    return SimpleNamespace(
        smtp_host="smtp.example.test",
        smtp_port=587,
        smtp_user="u",
        smtp_pass="p",
        smtp_from="noreply@example.test",
        alert_email_to="alerts@example.test",
        **extra,
    )


@pytest.mark.asyncio
async def test_digest_one_send_when_configured_and_prefs_on(db_session, engine):
    user = User(email="n4-on@example.com", hashed_password="x", display_name="N4")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        NotificationPreference(
            user=str(user.id),
            email_digest=True,
            in_app=True,
            fired_alerts=True,
        )
    )
    await create_notification(
        db_session,
        user_id=user.id,
        type="brief",
        title="Unread brief",
        body="body",
        link="/markets/nba-2025-01-15-lal-bos",
    )
    db_session.add(
        SignalEvent(
            signal_type="scanner:fired",
            platform="scanner",
            market_id="nba-2025-01-15-lal-bos",
            headline_eligible=True,
            payload={"title": "Fired pick"},
            created_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    sent: list[dict] = []

    def fake_send(*, to_addr, subject, body, settings=None, smtp_factory=None):
        sent.append({"to": to_addr, "subject": subject, "body": body})
        return True

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    summary = await send_notification_digest_task(
        {
            "settings": _smtp_on(),
            "session_factory": factory,
            "now": datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
            "send_fn": fake_send,
        }
    )
    assert summary["sent"] == 1
    assert len(sent) == 1
    assert sent[0]["to"] == "n4-on@example.com"
    assert "Paper research only — no execution" in sent[0]["body"]
    assert "Unread brief" in sent[0]["body"]
    assert "Fired pick" in sent[0]["body"]


@pytest.mark.asyncio
async def test_digest_zero_sends_when_prefs_off(db_session, engine):
    user = User(email="n4-off@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        NotificationPreference(
            user=str(user.id),
            email_digest=False,
            in_app=True,
            fired_alerts=True,
        )
    )
    await create_notification(
        db_session,
        user_id=user.id,
        type="brief",
        title="Should not email",
        body="x",
    )
    await db_session.commit()

    sent: list[dict] = []

    def fake_send(*, to_addr, subject, body, settings=None, smtp_factory=None):
        sent.append({"to": to_addr})
        return True

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    summary = await send_notification_digest_task(
        {
            "settings": _smtp_on(),
            "session_factory": factory,
            "now": datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
            "send_fn": fake_send,
        }
    )
    assert summary["sent"] == 0
    assert sent == []


@pytest.mark.asyncio
async def test_digest_skips_when_smtp_off(db_session, engine):
    user = User(email="n4-nosmtp@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    await create_notification(
        db_session,
        user_id=user.id,
        type="brief",
        title="Unread",
        body="x",
    )
    await db_session.commit()

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    summary = await send_notification_digest_task(
        {
            "settings": SimpleNamespace(
                smtp_host="",
                smtp_port=587,
                smtp_user="",
                smtp_pass="",
                smtp_from="",
                alert_email_to="",
            ),
            "session_factory": factory,
            "now": datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
        }
    )
    assert summary["sent"] == 0
    assert summary.get("skipped") is True


def test_compose_includes_paper_footer():
    note = Notification(
        user="u",
        type="brief",
        title="T",
        body="B",
        read=False,
    )
    body = compose_digest_body(unread=[note], fired=[])
    assert "Paper research only — no execution" in body
    assert "[brief] T" in body
