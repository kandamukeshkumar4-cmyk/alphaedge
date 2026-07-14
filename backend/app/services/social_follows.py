"""Authenticated follow relationships for the paper-trading social layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Follow, User
from app.services.analytics_leaderboard import anonymized_username
from app.services.social_profiles import get_public_trader_profile


class FollowTargetNotFound(ValueError):
    """The requested public trader does not exist or has opted out."""


class SelfFollowError(ValueError):
    """A user cannot follow their own public profile."""


@dataclass(frozen=True)
class FollowResult:
    username: str
    following: bool
    changed: bool
    followers_count: int


@dataclass(frozen=True)
class FollowingEntry:
    username: str
    member_since: datetime


async def _counts(db: AsyncSession, user_id: UUID) -> int:
    return int(
        await db.scalar(select(func.count(Follow.id)).where(Follow.followee_id == user_id)) or 0
    )


async def follow_trader(
    db: AsyncSession,
    follower_id: UUID,
    requested_name: str,
) -> FollowResult:
    profile = await get_public_trader_profile(db, requested_name)
    if profile is None:
        raise FollowTargetNotFound
    if profile.user_id == follower_id:
        raise SelfFollowError

    existing = await db.scalar(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followee_id == profile.user_id,
        )
    )
    changed = False
    if existing is None:
        db.add(Follow(follower_id=follower_id, followee_id=profile.user_id))
        try:
            await db.flush()
            changed = True
        except IntegrityError:
            # The unique constraint is the concurrency/idempotency authority;
            # another request may have inserted the same edge after the read.
            await db.rollback()
            existing = await db.scalar(
                select(Follow).where(
                    Follow.follower_id == follower_id,
                    Follow.followee_id == profile.user_id,
                )
            )
            if existing is None:
                raise

    return FollowResult(
        username=profile.username,
        following=True,
        changed=changed,
        followers_count=await _counts(db, profile.user_id),
    )


async def unfollow_trader(
    db: AsyncSession,
    follower_id: UUID,
    requested_name: str,
) -> FollowResult:
    profile = await get_public_trader_profile(db, requested_name)
    if profile is None:
        raise FollowTargetNotFound
    if profile.user_id == follower_id:
        raise SelfFollowError

    existing = await db.scalar(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followee_id == profile.user_id,
        )
    )
    changed = existing is not None
    if existing is not None:
        await db.delete(existing)
        await db.flush()

    return FollowResult(
        username=profile.username,
        following=False,
        changed=changed,
        followers_count=await _counts(db, profile.user_id),
    )


async def list_following(
    db: AsyncSession,
    follower_id: UUID,
    *,
    limit: int = 100,
) -> list[FollowingEntry]:
    result = await db.execute(
        select(Follow, User)
        .join(User, User.id == Follow.followee_id)
        .where(
            Follow.follower_id == follower_id,
            User.profile_public.is_(True),
        )
        .order_by(Follow.created_at.desc(), Follow.id.desc())
        .limit(limit)
    )
    return [
        FollowingEntry(
            username=anonymized_username(user.id, display_name=user.display_name),
            member_since=user.created_at,
        )
        for _, user in result.all()
    ]
