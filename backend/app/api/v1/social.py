"""Public paper-trader profiles for the social layer."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.activity import TradeActivityItem, TradeActivityPage
from app.api.v1.deps import get_current_user, get_optional_user
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
from app.services.social_service import (
    StoryNotFound,
    add_comment,
    list_comments,
    list_stories,
    toggle_reaction,
)

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


# ---------------------------------------------------------------------------
# Loop 104 — community stories / comments / reactions
# ---------------------------------------------------------------------------


class ActorOut(BaseModel):
    handle: str
    display_name: str
    avatar_url: str | None = None


class StoryOut(BaseModel):
    id: str
    kind: Literal["trade", "forecast", "watchlist", "note"]
    actor: ActorOut
    market_slug: str | None = None
    market_title: str | None = None
    headline: str
    body: str | None = None
    created_at: str
    reactions: dict[str, int]
    reacted: bool
    comment_count: int


class StoryPageOut(BaseModel):
    items: list[StoryOut]
    next_cursor: str | None = None


class CommentOut(BaseModel):
    id: str
    actor: ActorOut
    body: str
    created_at: str


class CommentListOut(BaseModel):
    items: list[CommentOut]


class CommentCreateBody(BaseModel):
    body: str = Field(..., min_length=1)

    @field_validator("body")
    @classmethod
    def _strip_and_cap(cls, value: str) -> str:
        text = value.strip()
        if not text or len(text) > 500:
            raise ValueError("body must be 1..500 characters after strip")
        return text


class ReactionBody(BaseModel):
    kind: Literal["like"] = "like"


class ReactionOut(BaseModel):
    reactions: dict[str, int]
    reacted: bool


@router.get("/stories", response_model=StoryPageOut, summary="List community stories")
async def get_stories(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=128),
    viewer: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> StoryPageOut:
    try:
        page = await list_stories(
            db,
            limit=limit,
            cursor=cursor,
            viewer_id=str(viewer.id) if viewer is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc
    return StoryPageOut(**page)


@router.get(
    "/stories/{story_id}/comments",
    response_model=CommentListOut,
    summary="List story comments",
)
async def get_story_comments(
    story_id: str = Path(min_length=1, max_length=128),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CommentListOut:
    try:
        page = await list_comments(db, story_id=story_id, limit=limit)
    except StoryNotFound as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    return CommentListOut(**page)


@router.post(
    "/stories/{story_id}/comments",
    response_model=CommentOut,
    summary="Add a story comment",
)
async def post_story_comment(
    body: CommentCreateBody,
    story_id: str = Path(min_length=1, max_length=128),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentOut:
    try:
        comment = await add_comment(
            db,
            story_id=story_id,
            user_id=str(current_user.id),
            body=body.body,
        )
    except StoryNotFound as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CommentOut(**comment)


@router.post(
    "/stories/{story_id}/reactions",
    response_model=ReactionOut,
    summary="React to a story (idempotent like)",
)
async def post_story_reaction(
    body: ReactionBody,
    story_id: str = Path(min_length=1, max_length=128),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReactionOut:
    try:
        result = await toggle_reaction(
            db,
            story_id=story_id,
            user_id=str(current_user.id),
            kind=body.kind,
            on=True,
        )
    except StoryNotFound as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ReactionOut(**result)


@router.delete(
    "/stories/{story_id}/reactions/like",
    response_model=ReactionOut,
    summary="Remove a like reaction",
)
async def delete_story_like(
    story_id: str = Path(min_length=1, max_length=128),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReactionOut:
    try:
        result = await toggle_reaction(
            db,
            story_id=story_id,
            user_id=str(current_user.id),
            kind="like",
            on=False,
        )
    except StoryNotFound as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    return ReactionOut(**result)
