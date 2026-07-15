"""Followed-trader activity feed built on the existing B4 activity payload."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Follow, PaperOrder, User
from app.services.analytics_activity import trade_activity_payload


@dataclass(frozen=True)
class SocialFeedPage:
    items: list[dict[str, Any]]
    next_cursor: str | None
    limit: int


def _offset_from_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
        if offset < 0:
            raise ValueError("negative")
        return offset
    except ValueError as exc:
        raise ValueError("Invalid cursor") from exc


async def list_followed_trader_activity(
    db: AsyncSession,
    follower_id: UUID,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> SocialFeedPage:
    """Return newest-first paper trades from followed public profiles only."""
    offset = _offset_from_cursor(cursor)
    rows = (
        await db.execute(
            select(PaperOrder, User.display_name)
            .join(Follow, Follow.followee_id == PaperOrder.user_id)
            .join(User, User.id == PaperOrder.user_id)
            .where(
                Follow.follower_id == follower_id,
                User.profile_public.is_(True),
            )
            .order_by(PaperOrder.created_at.desc(), PaperOrder.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )
    ).all()

    page = rows[:limit]
    items = [
        trade_activity_payload(
            order_id=str(order.id),
            user_id=order.user_id,
            slug=order.slug,
            side=order.side,
            outcome=order.outcome,
            shares=float(order.shares),
            price=float(order.price),
            action=order.action,
            created_at=order.created_at or datetime.now(timezone.utc),
            display_name=display_name,
        )
        for order, display_name in page
    ]
    return SocialFeedPage(
        items=items,
        next_cursor=str(offset + limit) if len(rows) > limit else None,
        limit=limit,
    )
