"""Loop V90 N2 — scanner/brief → in-app notification hooks.

Respects in_app (and fired_alerts for scanner:fired). Idempotent per
(user, type, link) within 1h. Paper research only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import (
    Notification,
    NotificationPreference,
    Scanner,
    ScannerRun,
    User,
    Watchlist,
)
from app.services.notification_producers import (
    notify_scanner_fired,
    notify_watchers_brief_created,
)
from app.services.scanner_alert_service import record_scanner_fired_alert


@pytest.mark.asyncio
async def test_scanner_fired_writes_in_app_notification(db_session):
    user = User(email="n2-scan@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    scanner = Scanner(
        name="NBA confluence",
        description="alert fixture",
        owner=str(user.id),
        spec={"schedule": {"interval_minutes": 30}, "steps": []},
        status="active",
        cooldown_minutes=0,
    )
    db_session.add(scanner)
    await db_session.flush()

    top = {
        "market_slug": "nba-2025-01-15-lal-bos",
        "title": "Lakers vs Celtics",
        "aligned": True,
    }
    run = ScannerRun(
        scanner_id=scanner.id,
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        result={
            "candidates": [top],
            "top_pick": top,
            "counts": {"universe": 1, "candidates": 1, "aligned": 1},
        },
    )
    db_session.add(run)
    await db_session.flush()

    event = await record_scanner_fired_alert(db_session, scanner, run)
    assert event is not None
    await db_session.commit()

    rows = (
        await db_session.scalars(
            select(Notification).where(
                Notification.user == str(user.id),
                Notification.type == "scanner:fired",
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].link == f"/scanners/{scanner.id}"
    assert rows[0].read is False


@pytest.mark.asyncio
async def test_scanner_notification_idempotent_within_1h(db_session):
    user = User(email="n2-idem@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    scanner = Scanner(
        name="Idem",
        description="d",
        owner=str(user.id),
        spec={"steps": []},
        status="active",
        cooldown_minutes=0,
    )
    db_session.add(scanner)
    await db_session.flush()
    run = ScannerRun(
        scanner_id=scanner.id,
        status="completed",
        result={"counts": {"aligned": 1}},
    )
    db_session.add(run)
    await db_session.flush()

    first = await notify_scanner_fired(
        scanner=scanner,
        run=run,
        market_slug="nba-2025-01-15-lal-bos",
        title="hit",
        session=db_session,
    )
    second = await notify_scanner_fired(
        scanner=scanner,
        run=run,
        market_slug="nba-2025-01-15-lal-bos",
        title="hit",
        session=db_session,
    )
    await db_session.commit()
    assert first == 1
    assert second == 0
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user == str(user.id))
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_scanner_skips_when_in_app_off(db_session):
    user = User(email="n2-off@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        NotificationPreference(
            user=str(user.id),
            email_digest=True,
            in_app=False,
            fired_alerts=True,
        )
    )
    scanner = Scanner(
        name="Off",
        description="d",
        owner=str(user.id),
        spec={"steps": []},
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()
    run = ScannerRun(scanner_id=scanner.id, status="completed", result={})
    db_session.add(run)
    await db_session.flush()

    n = await notify_scanner_fired(
        scanner=scanner,
        run=run,
        market_slug="nba-2025-01-15-lal-bos",
        title="hit",
        session=db_session,
    )
    await db_session.commit()
    assert n == 0
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user == str(user.id))
        )
    ).all()
    assert rows == []


@pytest.mark.asyncio
async def test_brief_notifies_watchlist_followers(db_session):
    watcher = User(email="n2-brief@example.com", hashed_password="x")
    stranger = User(email="n2-brief-x@example.com", hashed_password="x")
    db_session.add_all([watcher, stranger])
    await db_session.flush()
    slug = "nba-2025-01-15-lal-bos"
    db_session.add(Watchlist(user_id=watcher.id, slug=slug))
    await db_session.flush()

    brief_id = uuid4()
    n = await notify_watchers_brief_created(
        market_slug=slug,
        headline="Lakers lean",
        brief_id=brief_id,
        session=db_session,
    )
    await db_session.commit()
    assert n == 1

    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.type == "brief")
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].user == str(watcher.id)
    assert "Lakers lean" in rows[0].title
    assert str(brief_id) in (rows[0].link or "")

    # Idempotent within 1h
    n2 = await notify_watchers_brief_created(
        market_slug=slug,
        headline="Lakers lean",
        brief_id=brief_id,
        session=db_session,
    )
    assert n2 == 0
