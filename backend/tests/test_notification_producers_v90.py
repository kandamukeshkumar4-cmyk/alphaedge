"""Loop V90 N2 — scanner/brief notification producers + 1h idempotency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import (
    Notification,
    NotificationPreference,
    Scanner,
    ScannerRun,
    Subscription,
    User,
    Watchlist,
)
from app.services.notification_producers import (
    notify_scanner_fired,
    notify_watchers_brief_created,
)
from app.services.notification_service import create_notification_idempotent
from app.services.scanner_alert_service import record_scanner_fired_alert


async def _user(db_session, email: str) -> User:
    user = User(email=email, display_name="N2", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_idempotent_same_user_type_link_within_1h(db_session):
    user = await _user(db_session, "n2-idem@example.com")
    first = await create_notification_idempotent(
        db_session,
        user_id=user.id,
        type="scanner:fired",
        title="one",
        body="body",
        link="/scanners/x",
    )
    second = await create_notification_idempotent(
        db_session,
        user_id=user.id,
        type="scanner:fired",
        title="two",
        body="body",
        link="/scanners/x",
    )
    await db_session.commit()
    assert first is not None
    assert second is None
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user == str(user.id))
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_idempotent_allows_after_window(db_session):
    user = await _user(db_session, "n2-window@example.com")
    old = await create_notification_idempotent(
        db_session,
        user_id=user.id,
        type="brief",
        title="old",
        body="body",
        link="/markets/nba-2025-01-15-lal-bos",
        now=datetime.now(UTC) - timedelta(hours=2),
    )
    # Force created_at into the past (server_default would be now).
    assert old is not None
    old.created_at = datetime.now(UTC) - timedelta(hours=2)
    await db_session.flush()
    again = await create_notification_idempotent(
        db_session,
        user_id=user.id,
        type="brief",
        title="new",
        body="body",
        link="/markets/nba-2025-01-15-lal-bos",
    )
    await db_session.commit()
    assert again is not None
    assert again.id != old.id


@pytest.mark.asyncio
async def test_in_app_pref_false_skips_insert(db_session):
    user = await _user(db_session, "n2-pref@example.com")
    db_session.add(
        NotificationPreference(
            user=str(user.id),
            email_digest=True,
            in_app=False,
            fired_alerts=True,
        )
    )
    await db_session.flush()
    row = await create_notification_idempotent(
        db_session,
        user_id=user.id,
        type="brief",
        title="nope",
        body="body",
        link="/markets/x",
    )
    assert row is None


@pytest.mark.asyncio
async def test_notify_scanner_fired_owner_and_subscriber(db_session):
    owner = await _user(db_session, "n2-owner@example.com")
    sub_user = await _user(db_session, "n2-sub@example.com")
    scanner = Scanner(
        name="Edge hunter",
        owner=str(owner.id),
        spec={"universe": [], "steps": []},
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()
    db_session.add(
        Subscription(user=str(sub_user.id), ref_type="scanner", ref_id=scanner.id)
    )
    await db_session.flush()

    n = await notify_scanner_fired(
        scanner=scanner,
        run=None,
        market_slug="nba-2025-01-15-lal-bos",
        title="Edge hunter: Lakers",
        session=db_session,
    )
    await db_session.commit()
    assert n == 2
    types = (
        await db_session.scalars(select(Notification.type))
    ).all()
    assert types.count("scanner:fired") == 2


@pytest.mark.asyncio
async def test_record_scanner_fired_writes_notification(db_session):
    owner = await _user(db_session, "n2-rec@example.com")
    scanner = Scanner(
        name="Rec scanner",
        owner=str(owner.id),
        spec={},
        status="active",
        cooldown_minutes=0,
    )
    db_session.add(scanner)
    await db_session.flush()
    run = ScannerRun(
        scanner_id=scanner.id,
        status="ok",
        result={
            "counts": {"universe": 1, "candidates": 1, "aligned": 1},
            "top_pick": {
                "market_slug": "nba-2025-01-15-lal-bos",
                "title": "Lakers win",
            },
        },
    )
    db_session.add(run)
    await db_session.flush()

    event = await record_scanner_fired_alert(db_session, scanner, run)
    await db_session.commit()
    assert event is not None
    rows = (
        await db_session.scalars(
            select(Notification).where(
                Notification.user == str(owner.id),
                Notification.type == "scanner:fired",
            )
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_notify_brief_watchers(db_session):
    watcher = await _user(db_session, "n2-watch@example.com")
    stranger = await _user(db_session, "n2-stranger@example.com")
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
    row = await db_session.scalar(
        select(Notification).where(Notification.user == str(watcher.id))
    )
    assert row is not None
    assert row.type == "brief"
    assert str(brief_id) in (row.link or "")
    assert (
        await db_session.scalar(
            select(Notification).where(Notification.user == str(stranger.id))
        )
    ) is None
