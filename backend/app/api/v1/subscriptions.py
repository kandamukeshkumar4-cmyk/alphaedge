"""Community subscriptions — follow a skill or scanner (notify/track only)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import Scanner, Skill, Subscription, User
from app.db.session import get_db
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionOut

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])

_VALID_REF = {"skill", "scanner"}


async def _resolve_name(db: AsyncSession, ref_type: str, ref_id: UUID) -> str | None:
    if ref_type == "skill":
        skill = await db.scalar(select(Skill).where(Skill.id == ref_id))
        return skill.name if skill is not None else None
    scanner = await db.scalar(select(Scanner).where(Scanner.id == ref_id))
    return scanner.name if scanner is not None else None


async def _require_target(db: AsyncSession, ref_type: str, ref_id: UUID) -> str:
    name = await _resolve_name(db, ref_type, ref_id)
    if name is None:
        raise HTTPException(status_code=404, detail=f"{ref_type} not found")
    return name


def _out(sub: Subscription, name: str) -> SubscriptionOut:
    return SubscriptionOut(
        ref_type=sub.ref_type,  # type: ignore[arg-type]
        ref_id=sub.ref_id,
        name=name,
        created_at=sub.created_at,
    )


@router.post("/", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionOut:
    name = await _require_target(db, body.ref_type, body.ref_id)
    user_key = str(user.id)
    existing = await db.scalar(
        select(Subscription).where(
            Subscription.user == user_key,
            Subscription.ref_type == body.ref_type,
            Subscription.ref_id == body.ref_id,
        )
    )
    if existing is not None:
        return _out(existing, name)
    sub = Subscription(user=user_key, ref_type=body.ref_type, ref_id=body.ref_id)
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return _out(sub, name)


@router.delete("/{ref_type}/{ref_id}", response_model=list[SubscriptionOut])
async def delete_subscription(
    ref_type: str,
    ref_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SubscriptionOut]:
    if ref_type not in _VALID_REF:
        raise HTTPException(status_code=400, detail="ref_type must be skill or scanner")
    user_key = str(user.id)
    existing = await db.scalar(
        select(Subscription).where(
            Subscription.user == user_key,
            Subscription.ref_type == ref_type,
            Subscription.ref_id == ref_id,
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    return await _list_for_user(db, user_key)


@router.get("/", response_model=list[SubscriptionOut])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SubscriptionOut]:
    return await _list_for_user(db, str(user.id))


async def _list_for_user(db: AsyncSession, user_key: str) -> list[SubscriptionOut]:
    rows = (
        await db.scalars(
            select(Subscription)
            .where(Subscription.user == user_key)
            .order_by(Subscription.created_at.desc())
        )
    ).all()
    out: list[SubscriptionOut] = []
    for sub in rows:
        name = await _resolve_name(db, sub.ref_type, sub.ref_id)
        if name is None:
            name = "(deleted)"
        out.append(_out(sub, name))
    return out
