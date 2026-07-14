"""Public paper-trader profiles for the social layer."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.activity import TradeActivityItem, TradeActivityPage
from app.api.v1.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.social_follows import (
    FollowTargetNotFound,
    SelfFollowError,
    follow_trader,
    list_following,
    unfollow_trader,
)
from app.services.social_feed import list_followed_trader_activity
from app.services.social_profiles import get_public_trader_profile

router = APIRouter(prefix="/api/v1/social", tags=["social"])


class PublicTraderProfileResponse(BaseModel):
    username: str
    member_since: datetime
    trade_count: int
    settled_trade_count: int
    win_rate: float
    roi: float
    followers_count: int
    following_count: int
    paper_trading_only: bool = True


class FollowResponse(BaseModel):
    username: str
    following: bool
    changed: bool
    followers_count: int
    paper_trading_only: bool = True


class FollowingEntryResponse(BaseModel):
    username: str
    member_since: datetime


class FollowingResponse(BaseModel):
    items: list[FollowingEntryResponse]
    total: int
    paper_trading_only: bool = True


@router.get(
    "/traders/{trader}",
    response_model=PublicTraderProfileResponse,
    summary="Get a public trader profile",
    description="Return anonymized public stats for a paper trader without email or user ID fields.",
)
async def get_trader_profile(
    trader: str = Path(min_length=1, max_length=64, description="Anonymized label or display name"),
    db: AsyncSession = Depends(get_db),
) -> PublicTraderProfileResponse:
    profile = await get_public_trader_profile(db, trader)
    if profile is None:
        raise HTTPException(status_code=404, detail="Trader profile not found")
    return PublicTraderProfileResponse(
        username=profile.username,
        member_since=profile.member_since,
        trade_count=profile.trade_count,
        settled_trade_count=profile.settled_trade_count,
        win_rate=profile.win_rate,
        roi=profile.roi,
        followers_count=profile.followers_count,
        following_count=profile.following_count,
    )


@router.post(
    "/follow/{trader}",
    response_model=FollowResponse,
    summary="Follow a public trader",
    description="Follow a public paper trader by anonymized label or display name; repeated calls are idempotent.",
)
async def follow_public_trader(
    trader: str = Path(min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    try:
        result = await follow_trader(db, current_user.id, trader)
    except FollowTargetNotFound as exc:
        raise HTTPException(status_code=404, detail="Trader profile not found") from exc
    except SelfFollowError as exc:
        raise HTTPException(status_code=400, detail="You cannot follow yourself") from exc
    return FollowResponse(
        username=result.username,
        following=result.following,
        changed=result.changed,
        followers_count=result.followers_count,
    )


@router.delete(
    "/follow/{trader}",
    response_model=FollowResponse,
    summary="Unfollow a public trader",
    description="Remove a paper-trader follow edge; repeated calls are idempotent.",
)
async def unfollow_public_trader(
    trader: str = Path(min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    try:
        result = await unfollow_trader(db, current_user.id, trader)
    except FollowTargetNotFound as exc:
        raise HTTPException(status_code=404, detail="Trader profile not found") from exc
    except SelfFollowError as exc:
        raise HTTPException(status_code=400, detail="You cannot follow yourself") from exc
    return FollowResponse(
        username=result.username,
        following=result.following,
        changed=result.changed,
        followers_count=result.followers_count,
    )


@router.get(
    "/following",
    response_model=FollowingResponse,
    summary="List followed traders",
    description="List public paper traders followed by the authenticated user without identity fields.",
)
async def get_following(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowingResponse:
    items = await list_following(db, current_user.id)
    return FollowingResponse(
        items=[FollowingEntryResponse(username=i.username, member_since=i.member_since) for i in items],
        total=len(items),
    )


@router.get(
    "/feed",
    response_model=TradeActivityPage,
    summary="List followed-trader activity",
    description="Return anonymized recent paper trades from public traders followed by the authenticated user.",
)
async def get_social_feed(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TradeActivityPage:
    try:
        page = await list_followed_trader_activity(
            db,
            current_user.id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc
    return TradeActivityPage(
        items=[TradeActivityItem(**item) for item in page.items],
        next_cursor=page.next_cursor,
        limit=page.limit,
    )
