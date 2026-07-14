"""Loop V23 A2 — admin user list/search/detail + suspend/unsuspend."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.models import PaperOrder, User
from app.db.session import get_db
from app.events.bus import DomainEventBus

router = APIRouter(prefix="/api/v1/admin", tags=["admin-users"])


class AdminUserListItem(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    paper_balance: float
    is_suspended: bool
    onboarded: bool
    created_at: datetime | None = None
    trade_count: int = 0

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    users: list[AdminUserListItem]
    total: int
    limit: int
    offset: int
    paper_trading_only: bool = True


class AdminUserDetail(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    paper_balance: float
    is_suspended: bool
    onboarded: bool
    created_at: datetime | None = None
    trade_count: int
    total_volume: float
    flags: dict[str, bool]
    paper_trading_only: bool = True


class AdminUserActionResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_suspended: bool
    paper_trading_only: bool = True


def _balance_float(value: Decimal | float | int | None) -> float:
    return float(value if value is not None else 0)


@router.get("/users", response_model=AdminUserListResponse)
async def list_admin_users(
    q: str | None = Query(default=None, description="Search email or display_name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    """Paginated admin user list with optional email/display_name search."""
    filters = []
    if q is not None and (needle := q.strip()):
        pattern = f"%{needle}%"
        filters.append(
            or_(User.email.ilike(pattern), User.display_name.ilike(pattern))
        )

    count_stmt = select(func.count()).select_from(User)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int(await db.scalar(count_stmt) or 0)

    trade_count = (
        select(func.count(PaperOrder.id))
        .where(PaperOrder.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    stmt = (
        select(User, trade_count.label("trade_count"))
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if filters:
        stmt = stmt.where(*filters)

    rows = (await db.execute(stmt)).all()
    users = [
        AdminUserListItem(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            paper_balance=_balance_float(user.paper_balance),
            is_suspended=bool(user.is_suspended),
            onboarded=bool(user.onboarded),
            created_at=user.created_at,
            trade_count=int(tc or 0),
        )
        for user, tc in rows
    ]
    return AdminUserListResponse(
        users=users, total=total, limit=limit, offset=offset
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_admin_user(
    user_id: uuid.UUID,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    """Per-user admin detail: balance, trade count, flags."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    trade_count = int(
        await db.scalar(
            select(func.count()).select_from(PaperOrder).where(PaperOrder.user_id == user.id)
        )
        or 0
    )
    total_volume = Decimal(
        str(
            await db.scalar(
                select(func.coalesce(func.sum(PaperOrder.cost), 0)).where(
                    PaperOrder.user_id == user.id
                )
            )
            or 0
        )
    )
    return AdminUserDetail(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        paper_balance=_balance_float(user.paper_balance),
        is_suspended=bool(user.is_suspended),
        onboarded=bool(user.onboarded),
        created_at=user.created_at,
        trade_count=trade_count,
        total_volume=_balance_float(total_volume),
        flags={
            "is_suspended": bool(user.is_suspended),
            "onboarded": bool(user.onboarded),
        },
    )


@router.post("/users/{user_id}/suspend", response_model=AdminUserActionResponse)
async def suspend_admin_user(
    user_id: uuid.UUID,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminUserActionResponse:
    """Suspend a user — blocked from paper trading via RiskService + orders path."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already suspended"
        )
    user.is_suspended = True
    await db.flush()
    await DomainEventBus(db).emit(
        "user_suspended",
        {
            "user_id": str(user.id),
            "email": user.email,
            "is_suspended": True,
            "actor": "admin",
        },
    )
    return AdminUserActionResponse(
        id=user.id, email=user.email, is_suspended=True
    )


@router.post("/users/{user_id}/unsuspend", response_model=AdminUserActionResponse)
async def unsuspend_admin_user(
    user_id: uuid.UUID,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminUserActionResponse:
    """Clear suspension so the user can trade again."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is not suspended"
        )
    user.is_suspended = False
    await db.flush()
    await DomainEventBus(db).emit(
        "user_unsuspended",
        {
            "user_id": str(user.id),
            "email": user.email,
            "is_suspended": False,
            "actor": "admin",
        },
    )
    return AdminUserActionResponse(
        id=user.id, email=user.email, is_suspended=False
    )
