"""Loop V90 — in-app notification CRUD helpers (frozen FE contract).

``user`` is ``str(user.id)``. Producers may pass UUID; helpers normalize.
In-app only for the feed path — email digest / push store live elsewhere.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, NotificationPreference, PushSubscription

logger = logging.getLogger(__name__)

_MAX_TYPE = 24
_MAX_TITLE = 200
_MAX_BODY = 1000
_MAX_LINK = 300
_IDEMPOTENCY_WINDOW = timedelta(hours=1)


def _clip(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    return value[:max_len]


def _user_key(user: str | UUID | None = None, user_id: UUID | None = None) -> str:
    if user is not None:
        return str(user)
    if user_id is not None:
        return str(user_id)
    raise ValueError("user or user_id required")


async def get_preferences(
    session: AsyncSession, user: str | UUID
) -> NotificationPreference:
    """Return stored prefs or an unsaved defaults row (all True)."""
    key = str(user)
    row = await session.get(NotificationPreference, key)
    if row is not None:
        return row
    return NotificationPreference(
        user=key,
        email_digest=True,
        in_app=True,
        fired_alerts=True,
    )


async def upsert_preferences(
    session: AsyncSession,
    user: str | UUID,
    *,
    email_digest: bool,
    in_app: bool,
    fired_alerts: bool,
) -> NotificationPreference:
    key = str(user)
    row = await session.get(NotificationPreference, key)
    if row is None:
        row = NotificationPreference(user=key)
        session.add(row)
    row.email_digest = bool(email_digest)
    row.in_app = bool(in_app)
    row.fired_alerts = bool(fired_alerts)
    await session.flush()
    return row


async def create_notification(
    session: AsyncSession,
    *,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
    user: str | UUID | None = None,
    user_id: UUID | None = None,
) -> Notification:
    """Insert one notification row and flush. Caller owns the transaction."""
    row = Notification(
        user=_user_key(user, user_id),
        type=(type or "info")[:_MAX_TYPE],
        title=_clip(title, _MAX_TITLE) or "",
        body=_clip(body, _MAX_BODY) or "",
        link=_clip(link, _MAX_LINK),
        read=False,
    )
    session.add(row)
    await session.flush()
    return row


async def recent_duplicate(
    session: AsyncSession,
    *,
    user: str | UUID,
    type: str,
    link: str | None,
    window: timedelta = _IDEMPOTENCY_WINDOW,
    now: datetime | None = None,
) -> Notification | None:
    """Return an existing row with same (user, type, link) inside the window."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    since = current - window
    stmt = select(Notification).where(
        Notification.user == str(user),
        Notification.type == (type or "")[:_MAX_TYPE],
        Notification.created_at >= since,
    )
    if link is None:
        stmt = stmt.where(Notification.link.is_(None))
    else:
        stmt = stmt.where(Notification.link == link[:_MAX_LINK])
    return await session.scalar(stmt.order_by(Notification.created_at.desc()).limit(1))


async def create_notification_idempotent(
    session: AsyncSession,
    *,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
    user: str | UUID | None = None,
    user_id: UUID | None = None,
    require_in_app: bool = True,
    now: datetime | None = None,
) -> Notification | None:
    """Insert unless prefs block or a duplicate exists within 1h."""
    key = _user_key(user, user_id)
    if require_in_app:
        prefs = await get_preferences(session, key)
        if not prefs.in_app:
            return None
        if type == "scanner:fired" and not prefs.fired_alerts:
            return None
    clipped_link = _clip(link, _MAX_LINK)
    existing = await recent_duplicate(
        session, user=key, type=type, link=clipped_link, now=now
    )
    if existing is not None:
        return existing
    return await create_notification(
        session,
        user=key,
        type=type,
        title=title,
        body=body,
        link=clipped_link,
    )


async def create_notification_best_effort(
    *,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
    user: str | UUID | None = None,
    user_id: UUID | None = None,
    session: AsyncSession | None = None,
    publish_ws: bool = True,
    idempotent: bool = False,
) -> Notification | None:
    """Create a notification without raising into the caller's transaction."""
    try:
        async def _write(db: AsyncSession) -> Notification | None:
            if idempotent:
                return await create_notification_idempotent(
                    db,
                    user=user,
                    user_id=user_id,
                    type=type,
                    title=title,
                    body=body,
                    link=link,
                )
            return await create_notification(
                db,
                user=user,
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                link=link,
            )

        if session is not None:
            async with session.begin_nested():
                row = await _write(session)
            if row is not None and publish_ws:
                await _publish_new_notification(row)
            return row

        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as own:
            row = await _write(own)
            await own.commit()
            if row is not None and publish_ws:
                await _publish_new_notification(row)
            return row
    except Exception:  # noqa: BLE001 — producers must never raise
        logger.warning(
            "notification create failed type=%s user=%s",
            type,
            user if user is not None else user_id,
            exc_info=True,
        )
        return None


async def _publish_new_notification(row: Notification) -> None:
    """Fan onto the multiplex hub ``notifications`` channel (never raises)."""
    try:
        from app.core.broadcast import hub

        await hub.publish(
            "notifications",
            {
                "type": "notification",
                "id": str(row.id),
                "user_id": row.user,
                "notification_type": row.type,
                "title": row.title,
                "body": row.body,
                "link": row.link,
                "created_at": (
                    row.created_at.isoformat()
                    if row.created_at is not None
                    else datetime.now(UTC).isoformat()
                ),
            },
        )
    except Exception:  # noqa: BLE001
        return


async def unread_count(session: AsyncSession, user: str | UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user == str(user), Notification.read.is_(False))
    )
    return int(count or 0)


async def list_notifications(
    session: AsyncSession,
    user: str | UUID,
    *,
    limit: int = 30,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[Notification], int]:
    """Newest-first page + total unread for the badge."""
    key = str(user)
    stmt = select(Notification).where(Notification.user == key)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    stmt = (
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    badge = await unread_count(session, key)
    return rows, badge


async def mark_read(
    session: AsyncSession,
    user: str | UUID,
    notification_id: UUID,
) -> Notification | None:
    """Mark one notification read. Idempotent; returns None if missing/not owned."""
    row = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user == str(user),
        )
    )
    if row is None:
        return None
    if not row.read:
        row.read = True
        await session.flush()
    return row


async def mark_all_read(session: AsyncSession, user: str | UUID) -> int:
    """Mark all unread notifications read. Idempotent; returns rows updated."""
    rows = list(
        (
            await session.scalars(
                select(Notification).where(
                    Notification.user == str(user),
                    Notification.read.is_(False),
                )
            )
        ).all()
    )
    for row in rows:
        row.read = True
    if rows:
        await session.flush()
    return len(rows)


async def store_push_subscription(
    session: AsyncSession,
    user: str | UUID,
    subscription: dict[str, Any],
) -> PushSubscription:
    """Persist a web-push subscription JSON blob (no external send)."""
    row = PushSubscription(user=str(user), subscription=dict(subscription))
    session.add(row)
    await session.flush()
    return row


def notification_to_dict(row: Notification) -> dict[str, Any]:
    created = row.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return {
        "id": str(row.id),
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "link": row.link,
        "read": bool(row.read),
        "created_at": created.isoformat() if created else None,
    }
