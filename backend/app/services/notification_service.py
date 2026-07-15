"""Loop V24 — in-app notification CRUD helpers.

In-app only (no email/telegram/push). Producers should prefer
``create_notification_best_effort`` so a fan-out failure never raises into the
producing transaction (mirrors ``publish_paper_trade_activity``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification

logger = logging.getLogger(__name__)

_MAX_TITLE = 256
_MAX_BODY = 4000
_MAX_LINK = 512


def _clip(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    return value[:max_len]


async def create_notification(
    session: AsyncSession,
    *,
    user_id: UUID,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
) -> Notification:
    """Insert one notification row and flush. Caller owns the transaction."""
    row = Notification(
        user_id=user_id,
        type=(type or "info")[:64],
        title=_clip(title, _MAX_TITLE) or "",
        body=_clip(body, _MAX_BODY) or "",
        link=_clip(link, _MAX_LINK),
    )
    session.add(row)
    await session.flush()
    return row


async def create_notification_best_effort(
    *,
    user_id: UUID,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
    session: AsyncSession | None = None,
    publish_ws: bool = True,
) -> Notification | None:
    """Create a notification without raising into the caller's transaction.

    When ``session`` is None, uses a dedicated short-lived session so a failure
    cannot poison the producing unit of work. When a session is provided, wraps
    the write in try/except only (caller still owns commit).
    """
    try:
        if session is not None:
            # Savepoint so a flush failure cannot poison the producing txn.
            async with session.begin_nested():
                row = await create_notification(
                    session,
                    user_id=user_id,
                    type=type,
                    title=title,
                    body=body,
                    link=link,
                )
            if publish_ws:
                await _publish_new_notification(row)
            return row

        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as own:
            row = await create_notification(
                own,
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                link=link,
            )
            await own.commit()
            if publish_ws:
                await _publish_new_notification(row)
            return row
    except Exception:  # noqa: BLE001 — producers must never raise
        logger.warning(
            "notification create failed type=%s user=%s",
            type,
            user_id,
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
                "user_id": str(row.user_id),
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


async def unread_count(session: AsyncSession, user_id: UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return int(count or 0)


async def list_notifications(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[Notification], int]:
    """Newest-first page + total unread for the badge."""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = (
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    badge = await unread_count(session, user_id)
    return rows, badge


async def mark_read(
    session: AsyncSession,
    user_id: UUID,
    notification_id: UUID,
) -> Notification | None:
    """Mark one notification read. Idempotent; returns None if missing/not owned."""
    row = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await session.flush()
    return row


async def mark_all_read(session: AsyncSession, user_id: UUID) -> int:
    """Mark all unread notifications read. Idempotent; returns rows updated.

    Updates ORM instances in the identity map (not a bulk UPDATE with
    ``synchronize_session=False``) so a subsequent list in the same session
    sees ``read_at`` / ``unread=False`` without a refresh race (SEC-Z2-02).
    """
    now = datetime.now(UTC)
    rows = list(
        (
            await session.scalars(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
        ).all()
    )
    for row in rows:
        row.read_at = now
    if rows:
        await session.flush()
    return len(rows)


def notification_to_dict(row: Notification) -> dict[str, Any]:
    created = row.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    read_at = row.read_at
    if read_at is not None and read_at.tzinfo is None:
        read_at = read_at.replace(tzinfo=UTC)
    return {
        "id": str(row.id),
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "link": row.link,
        "read_at": read_at.isoformat() if read_at else None,
        "created_at": created.isoformat() if created else None,
        "unread": row.read_at is None,
    }
