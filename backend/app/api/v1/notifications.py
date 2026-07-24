"""Loop V90 — in-app notification center (frozen FE contract).

Routes:
    GET  /api/v1/notifications?limit=30
         -> {"items":[{id,type,title,body,read,created_at,link}],"unread":N}
    POST /api/v1/notifications/{id}/read -> 204
    POST /api/v1/notifications/read-all  -> {"marked":N}
    GET  /api/v1/notifications/preferences
    PUT  /api/v1/notifications/preferences
    POST /api/v1/notifications/push/subscribe -> {"stored":true}

AUTHED (JWT). Paper research only — no order path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services import notification_service as svc

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    read: bool
    created_at: datetime | None = None
    link: str | None = None

    model_config = {"from_attributes": True}


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread: int


class MarkedOut(BaseModel):
    marked: int


class PreferencesOut(BaseModel):
    email_digest: bool
    in_app: bool
    fired_alerts: bool


class PreferencesUpdate(BaseModel):
    email_digest: bool
    in_app: bool
    fired_alerts: bool


class PushSubscribeIn(BaseModel):
    subscription: dict[str, Any] = Field(default_factory=dict)


class PushSubscribeOut(BaseModel):
    stored: bool = True


def _to_out(row) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        type=row.type,
        title=row.title,
        body=row.body,
        read=bool(row.read),
        created_at=row.created_at,
        link=row.link,
    )


@router.get(
    "",
    response_model=NotificationListOut,
    summary="List the caller's in-app notifications",
)
async def list_my_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    rows, badge = await svc.list_notifications(
        db,
        current_user.id,
        limit=limit,
        offset=0,
    )
    page = rows[:limit]
    return NotificationListOut(
        items=[_to_out(r) for r in page],
        unread=badge,
    )


@router.post(
    "/read-all",
    response_model=MarkedOut,
    summary="Mark all of the caller's notifications as read",
)
async def read_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkedOut:
    marked = await svc.mark_all_read(db, current_user.id)
    await db.commit()
    return MarkedOut(marked=marked)


@router.get(
    "/preferences",
    response_model=PreferencesOut,
    summary="Get notification channel preferences",
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    prefs = await svc.get_preferences(db, current_user.id)
    return PreferencesOut(
        email_digest=bool(prefs.email_digest),
        in_app=bool(prefs.in_app),
        fired_alerts=bool(prefs.fired_alerts),
    )


@router.put(
    "/preferences",
    response_model=PreferencesOut,
    summary="Replace notification channel preferences",
)
async def put_preferences(
    body: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    prefs = await svc.upsert_preferences(
        db,
        current_user.id,
        email_digest=body.email_digest,
        in_app=body.in_app,
        fired_alerts=body.fired_alerts,
    )
    await db.commit()
    return PreferencesOut(
        email_digest=bool(prefs.email_digest),
        in_app=bool(prefs.in_app),
        fired_alerts=bool(prefs.fired_alerts),
    )


@router.post(
    "/push/subscribe",
    response_model=PushSubscribeOut,
    summary="Store a web-push subscription JSON (no send in v1)",
)
async def push_subscribe(
    body: PushSubscribeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushSubscribeOut:
    await svc.store_push_subscription(db, current_user.id, body.subscription)
    await db.commit()
    return PushSubscribeOut(stored=True)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Mark one notification as read (idempotent)",
)
async def read_one_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await svc.mark_read(db, current_user.id, notification_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
