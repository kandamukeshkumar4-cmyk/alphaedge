"""Loop V24 N1 — in-app notification center API.

Routes:
    GET  /api/v1/notifications              cursor-paginated list + unread_count
    POST /api/v1/notifications/read-all     mark all read (idempotent)
    POST /api/v1/notifications/{id}/read    mark one read (idempotent)

AUTHED (JWT). In-app only — no email/SMS/push/webhook delivery.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services import notification_service as svc

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

NOTIFICATIONS_DISCLAIMER = (
    "In-app notifications only. Simulated funds — no email, SMS, or push delivery."
)


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime | None = None
    unread: bool

    model_config = {"from_attributes": True}


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None = None
    limit: int
    unread_count: int
    paper_trading_only: bool = True
    disclaimer: str = NOTIFICATIONS_DISCLAIMER


class NotificationReadOut(BaseModel):
    id: UUID
    read_at: datetime | None = None
    paper_trading_only: bool = True


class NotificationReadAllOut(BaseModel):
    marked: int = Field(description="Rows newly marked read this call")
    paper_trading_only: bool = True


def _to_out(row) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        type=row.type,
        title=row.title,
        body=row.body,
        link=row.link,
        read_at=row.read_at,
        created_at=row.created_at,
        unread=row.read_at is None,
    )


@router.get(
    "",
    response_model=NotificationListOut,
    summary="List the caller's in-app notifications",
)
async def list_my_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    """Newest-first cursor page. Cursor is an opaque offset (str(int))."""
    offset = 0
    if cursor is not None:
        try:
            offset = int(cursor)
            if offset < 0:
                raise ValueError("negative")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor") from exc

    rows, badge = await svc.list_notifications(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    page = rows[:limit]
    next_cursor = str(offset + limit) if len(rows) > limit else None
    return NotificationListOut(
        items=[_to_out(r) for r in page],
        next_cursor=next_cursor,
        limit=limit,
        unread_count=badge,
        paper_trading_only=True,
        disclaimer=NOTIFICATIONS_DISCLAIMER,
    )


@router.post(
    "/read-all",
    response_model=NotificationReadAllOut,
    summary="Mark all of the caller's notifications as read",
)
async def read_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationReadAllOut:
    marked = await svc.mark_all_read(db, current_user.id)
    await db.commit()
    return NotificationReadAllOut(marked=marked, paper_trading_only=True)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationReadOut,
    summary="Mark one notification as read (idempotent)",
)
async def read_one_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationReadOut:
    row = await svc.mark_read(db, current_user.id, notification_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    await db.commit()
    return NotificationReadOut(
        id=row.id,
        read_at=row.read_at,
        paper_trading_only=True,
    )
