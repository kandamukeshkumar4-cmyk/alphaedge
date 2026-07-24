"""Loop 104 — community social service (derived stories + engagement).

Stories are assembled read-only from existing paper-trade and watchlist activity.
Comments / reactions / watchlist-share visibility are the only mutable rows.
Never imports RiskService or OrderBookService. Comment bodies are plain text only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, PaperOrder, User, Watchlist
from app.models.social import StoryComment, StoryReaction, WatchlistShare
from app.services.analytics_activity import public_trader_label

_STORY_PREFIX_TRADE = "trade:"
_STORY_PREFIX_WATCHLIST = "watchlist:"


class StoryNotFound(Exception):
    """Raised when a story_id does not resolve to derived activity."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _parse_cursor(cursor: str | None) -> datetime | None:
    if cursor is None or not cursor.strip():
        return None
    raw = cursor.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Invalid cursor") from exc
    return _as_utc(parsed)


def _actor_dict(user_id: UUID, display_name: str | None) -> dict[str, Any]:
    handle = public_trader_label(user_id, display_name=display_name)
    name = display_name.strip() if display_name and display_name.strip() else handle
    return {"handle": handle, "display_name": name, "avatar_url": None}


def _trade_story_id(order_id: UUID) -> str:
    return f"{_STORY_PREFIX_TRADE}{order_id}"


def _watchlist_story_id(entry_id: UUID) -> str:
    return f"{_STORY_PREFIX_WATCHLIST}{entry_id}"


def _trade_headline(side: str, outcome: str, shares: float, price: float, slug: str) -> str:
    return (
        f"{side.upper()} {outcome.lower()} {shares:g} @ {price:g} on {slug}"
    )


async def _market_titles(db: AsyncSession, slugs: list[str]) -> dict[str, str]:
    if not slugs:
        return {}
    rows = (
        await db.execute(select(Market.slug, Market.title).where(Market.slug.in_(slugs)))
    ).all()
    return {slug: title for slug, title in rows}


async def _reaction_stats(
    db: AsyncSession,
    story_ids: list[str],
    viewer_id: str | None,
) -> dict[str, tuple[int, bool]]:
    """Return story_id -> (like_count, reacted_by_viewer)."""
    if not story_ids:
        return {}
    counts = dict.fromkeys(story_ids, 0)
    rows = (
        await db.execute(
            select(StoryReaction.story_id, func.count())
            .where(
                StoryReaction.story_id.in_(story_ids),
                StoryReaction.kind == "like",
            )
            .group_by(StoryReaction.story_id)
        )
    ).all()
    for story_id, count in rows:
        counts[str(story_id)] = int(count)

    reacted: set[str] = set()
    if viewer_id:
        try:
            viewer_uuid = UUID(viewer_id)
        except ValueError:
            viewer_uuid = None
        if viewer_uuid is not None:
            reacted_rows = (
                await db.execute(
                    select(StoryReaction.story_id).where(
                        StoryReaction.story_id.in_(story_ids),
                        StoryReaction.user_id == viewer_uuid,
                        StoryReaction.kind == "like",
                    )
                )
            ).scalars().all()
            reacted = {str(sid) for sid in reacted_rows}

    return {sid: (counts[sid], sid in reacted) for sid in story_ids}


async def _comment_counts(db: AsyncSession, story_ids: list[str]) -> dict[str, int]:
    if not story_ids:
        return {}
    out = dict.fromkeys(story_ids, 0)
    rows = (
        await db.execute(
            select(StoryComment.story_id, func.count())
            .where(StoryComment.story_id.in_(story_ids))
            .group_by(StoryComment.story_id)
        )
    ).all()
    for story_id, count in rows:
        out[str(story_id)] = int(count)
    return out


async def _story_exists(db: AsyncSession, story_id: str) -> bool:
    if story_id.startswith(_STORY_PREFIX_TRADE):
        raw = story_id[len(_STORY_PREFIX_TRADE) :]
        try:
            order_id = UUID(raw)
        except ValueError:
            return False
        return (
            await db.scalar(select(PaperOrder.id).where(PaperOrder.id == order_id))
        ) is not None
    if story_id.startswith(_STORY_PREFIX_WATCHLIST):
        raw = story_id[len(_STORY_PREFIX_WATCHLIST) :]
        try:
            entry_id = UUID(raw)
        except ValueError:
            return False
        return (
            await db.scalar(select(Watchlist.id).where(Watchlist.id == entry_id))
        ) is not None
    return False


async def _ensure_story(db: AsyncSession, story_id: str) -> None:
    if not await _story_exists(db, story_id):
        raise StoryNotFound(story_id)


async def list_stories(
    db: AsyncSession,
    *,
    limit: int = 20,
    cursor: str | None = None,
    viewer_id: str | None = None,
) -> dict:
    """Derived reverse-chronological stories from paper trades + watchlist adds."""
    cursor_at = _parse_cursor(cursor)
    fetch_n = max(limit * 3, limit + 1)

    trade_stmt = (
        select(PaperOrder, User.display_name)
        .join(User, User.id == PaperOrder.user_id)
        .where(User.profile_public.is_(True))
        .order_by(PaperOrder.created_at.desc(), PaperOrder.id.desc())
        .limit(fetch_n)
    )
    if cursor_at is not None:
        trade_stmt = trade_stmt.where(PaperOrder.created_at < cursor_at)

    watch_stmt = (
        select(Watchlist, User.display_name)
        .join(User, User.id == Watchlist.user_id)
        .where(User.profile_public.is_(True))
        .order_by(Watchlist.created_at.desc(), Watchlist.id.desc())
        .limit(fetch_n)
    )
    if cursor_at is not None:
        watch_stmt = watch_stmt.where(Watchlist.created_at < cursor_at)

    trade_rows = (await db.execute(trade_stmt)).all()
    watch_rows = (await db.execute(watch_stmt)).all()

    slugs = [o.slug for o, _ in trade_rows] + [w.slug for w, _ in watch_rows]
    titles = await _market_titles(db, list({s for s in slugs if s}))

    candidates: list[dict[str, Any]] = []
    for order, display_name in trade_rows:
        created = order.created_at or datetime.now(UTC)
        story_id = _trade_story_id(order.id)
        candidates.append(
            {
                "id": story_id,
                "kind": "trade",
                "actor": _actor_dict(order.user_id, display_name),
                "market_slug": order.slug,
                "market_title": titles.get(order.slug),
                "headline": _trade_headline(
                    order.side, order.outcome, float(order.shares), float(order.price), order.slug
                ),
                "body": None,
                "created_at": _iso(created),
                "_sort_at": _as_utc(created),
                "_sort_id": story_id,
            }
        )
    for entry, display_name in watch_rows:
        created = entry.created_at or datetime.now(UTC)
        story_id = _watchlist_story_id(entry.id)
        title = titles.get(entry.slug)
        candidates.append(
            {
                "id": story_id,
                "kind": "watchlist",
                "actor": _actor_dict(entry.user_id, display_name),
                "market_slug": entry.slug,
                "market_title": title,
                "headline": f"Added {title or entry.slug} to watchlist",
                "body": None,
                "created_at": _iso(created),
                "_sort_at": _as_utc(created),
                "_sort_id": story_id,
            }
        )

    candidates.sort(key=lambda s: (s["_sort_at"], s["_sort_id"]), reverse=True)
    page = candidates[:limit]
    next_cursor = page[-1]["created_at"] if len(candidates) > limit else None

    story_ids = [s["id"] for s in page]
    reaction_map = await _reaction_stats(db, story_ids, viewer_id)
    comment_map = await _comment_counts(db, story_ids)

    items: list[dict[str, Any]] = []
    for raw in page:
        like_count, reacted = reaction_map.get(raw["id"], (0, False))
        items.append(
            {
                "id": raw["id"],
                "kind": raw["kind"],
                "actor": raw["actor"],
                "market_slug": raw["market_slug"],
                "market_title": raw["market_title"],
                "headline": raw["headline"],
                "body": raw["body"],
                "created_at": raw["created_at"],
                "reactions": {"like": like_count},
                "reacted": bool(reacted) if viewer_id else False,
                "comment_count": comment_map.get(raw["id"], 0),
            }
        )
    return {"items": items, "next_cursor": next_cursor}


async def list_comments(
    db: AsyncSession,
    *,
    story_id: str,
    limit: int = 50,
) -> dict:
    await _ensure_story(db, story_id)
    rows = (
        await db.execute(
            select(StoryComment, User.display_name)
            .join(User, User.id == StoryComment.user_id)
            .where(StoryComment.story_id == story_id)
            .order_by(StoryComment.created_at.desc(), StoryComment.id.desc())
            .limit(limit)
        )
    ).all()
    items = [
        {
            "id": comment.id,
            "actor": _actor_dict(comment.user_id, display_name),
            "body": comment.body,
            "created_at": _iso(comment.created_at),
        }
        for comment, display_name in rows
    ]
    return {"items": items}


async def add_comment(
    db: AsyncSession,
    *,
    story_id: str,
    user_id: str,
    body: str,
) -> dict:
    await _ensure_story(db, story_id)
    text = body.strip()
    if not text or len(text) > 500:
        raise ValueError("body must be 1..500 chars after strip")
    user_uuid = UUID(user_id)
    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None:
        raise ValueError("user not found")
    comment = StoryComment(
        id=str(uuid4()),
        story_id=story_id,
        user_id=user_uuid,
        body=text,
    )
    db.add(comment)
    await db.flush()
    return {
        "id": comment.id,
        "actor": _actor_dict(user.id, user.display_name),
        "body": comment.body,
        "created_at": _iso(comment.created_at or datetime.now(UTC)),
    }


async def _reaction_payload(
    db: AsyncSession,
    *,
    story_id: str,
    user_id: UUID,
    kind: str,
) -> dict:
    like_count = int(
        await db.scalar(
            select(func.count())
            .select_from(StoryReaction)
            .where(StoryReaction.story_id == story_id, StoryReaction.kind == kind)
        )
        or 0
    )
    reacted = (
        await db.scalar(
            select(StoryReaction.id).where(
                StoryReaction.story_id == story_id,
                StoryReaction.user_id == user_id,
                StoryReaction.kind == kind,
            )
        )
    ) is not None
    return {"reactions": {"like": like_count}, "reacted": reacted}


async def toggle_reaction(
    db: AsyncSession,
    *,
    story_id: str,
    user_id: str,
    kind: str,
    on: bool,
) -> dict:
    await _ensure_story(db, story_id)
    if kind != "like":
        raise ValueError("unsupported reaction kind")
    user_uuid = UUID(user_id)
    existing = await db.scalar(
        select(StoryReaction).where(
            StoryReaction.story_id == story_id,
            StoryReaction.user_id == user_uuid,
            StoryReaction.kind == kind,
        )
    )
    if on:
        if existing is None:
            db.add(
                StoryReaction(
                    id=str(uuid4()),
                    story_id=story_id,
                    user_id=user_uuid,
                    kind=kind,
                )
            )
            await db.flush()
    else:
        if existing is not None:
            await db.delete(existing)
            await db.flush()
    return await _reaction_payload(db, story_id=story_id, user_id=user_uuid, kind=kind)


async def _resolve_user_by_handle(db: AsyncSession, handle: str) -> User | None:
    requested = handle.strip().casefold()
    if not requested:
        return None
    users = (await db.execute(select(User))).scalars().all()
    matches = [
        u
        for u in users
        if public_trader_label(u.id, display_name=u.display_name).casefold() == requested
    ]
    if len(matches) != 1:
        return None
    return matches[0]


async def get_shared_watchlist(db: AsyncSession, *, handle: str) -> dict | None:
    user = await _resolve_user_by_handle(db, handle)
    if user is None:
        return None
    share = await db.scalar(
        select(WatchlistShare).where(WatchlistShare.user_id == user.id)
    )
    if share is None or not share.public:
        return None
    rows = (
        await db.execute(
            select(Watchlist, Market.title)
            .outerjoin(Market, Market.slug == Watchlist.slug)
            .where(Watchlist.user_id == user.id)
            .order_by(Watchlist.created_at.desc(), Watchlist.id.desc())
        )
    ).all()
    actor = _actor_dict(user.id, user.display_name)
    items = [
        {
            "market_slug": entry.slug,
            "market_title": title or entry.slug,
            "added_at": _iso(entry.created_at or datetime.now(UTC)),
        }
        for entry, title in rows
    ]
    return {
        "handle": actor["handle"],
        "display_name": actor["display_name"],
        "items": items,
    }


async def set_watchlist_share(db: AsyncSession, *, user_id: str, public: bool) -> dict:
    user_uuid = UUID(user_id)
    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None:
        raise ValueError("user not found")
    share = await db.scalar(
        select(WatchlistShare).where(WatchlistShare.user_id == user_uuid)
    )
    now = datetime.now(UTC)
    if share is None:
        share = WatchlistShare(user_id=user_uuid, public=public, updated_at=now)
        db.add(share)
    else:
        share.public = public
        share.updated_at = now
    await db.flush()
    handle = public_trader_label(user.id, display_name=user.display_name)
    return {
        "public": bool(share.public),
        "share_url": f"/watchlist/shared/{handle}",
    }
