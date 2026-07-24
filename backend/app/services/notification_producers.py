"""Loop V24 N2 — fan domain events into per-user in-app notifications.

Never raises into the producing transaction (same contract as
``publish_paper_trade_activity``). In-app only — no email/push.

Sources:
* paper order fill / close (B4 path) — always has ``user_id``
* CLOB cancel (A3) — notifies only when a User can be resolved from account
* followed-trader trade — skipped gracefully when V22 social tables are absent
* drift/ops alerts — mirrored to configured admin emails only (reuses
  AlertDispatchService; no parallel alert system)
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# Ops/drift alert families that fan to admin notification inboxes only.
# Match both prefix forms (ops_*) and suffix forms (*_drift, calibration_drift).
_ADMIN_ALERT_PREFIXES = ("ops_", "drift")
_ADMIN_ALERT_CONTAINS = ("drift",)


def _is_admin_alert_type(alert_type: str) -> bool:
    t = (alert_type or "").lower()
    if any(t.startswith(p) for p in _ADMIN_ALERT_PREFIXES):
        return True
    return any(token in t for token in _ADMIN_ALERT_CONTAINS)


def _admin_emails(settings=None) -> list[str]:
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    raw = getattr(settings, "notification_admin_emails", "") or ""
    return [e.strip().lower() for e in str(raw).split(",") if e.strip()]


async def notify_order_filled(
    *,
    user_id: UUID,
    order_id: str,
    slug: str,
    side: str,
    outcome: str,
    shares: float,
    price: float,
    action: str = "BUY",
    session=None,
) -> None:
    """Paper / known-user fill → per-user notification. Never raises."""
    try:
        from app.services.notification_service import create_notification_best_effort

        action_u = (action or "BUY").upper()
        title = f"Order {action_u.lower()} filled"
        body = (
            f"{action_u} {shares:g} {outcome.upper()} on {slug} "
            f"@ {price:.4f} (order {order_id[:8]})"
        )
        await create_notification_best_effort(
            user_id=user_id,
            type="order_filled",
            title=title,
            body=body,
            link=f"/markets/{slug}",
            session=session,
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify_order_filled failed", exc_info=True)


async def notify_order_cancelled(
    *,
    user_id: UUID | None,
    order_id: str,
    market_id: str | None = None,
    remaining_quantity: str | None = None,
) -> None:
    """CLOB cancel → per-user notification when ``user_id`` is known. Never raises."""
    if user_id is None:
        return
    try:
        from app.services.notification_service import create_notification_best_effort

        rem = remaining_quantity or "?"
        title = "Order cancelled"
        body = f"Order {order_id[:8]} cancelled (remaining {rem})"
        link = f"/markets/{market_id}" if market_id else None
        await create_notification_best_effort(
            user_id=user_id,
            type="order_cancelled",
            title=title,
            body=body,
            link=link,
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify_order_cancelled failed", exc_info=True)


async def resolve_user_id_for_account(account_id: UUID) -> UUID | None:
    """Best-effort Account → User map. No stable FK exists; try email=name match."""
    try:
        from sqlalchemy import select

        from app.db.models import Account, User
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            account = await session.scalar(
                select(Account).where(Account.id == account_id)
            )
            if account is None or not account.name:
                return None
            user = await session.scalar(
                select(User).where(User.email == account.name)
            )
            return user.id if user is not None else None
    except Exception:  # noqa: BLE001
        return None


async def notify_clob_order_cancelled(payload: dict[str, Any]) -> None:
    """Hook for A3 cancel_order event payloads. Never raises."""
    try:
        order_id = str(payload.get("order_id") or "")
        account_id_raw = payload.get("account_id")
        user_id: UUID | None = None
        if account_id_raw:
            try:
                user_id = await resolve_user_id_for_account(UUID(str(account_id_raw)))
            except Exception:  # noqa: BLE001
                user_id = None
        await notify_order_cancelled(
            user_id=user_id,
            order_id=order_id,
            market_id=str(payload.get("market_id") or "") or None,
            remaining_quantity=(
                str(payload["remaining_quantity"])
                if payload.get("remaining_quantity") is not None
                else None
            ),
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify_clob_order_cancelled failed", exc_info=True)


def social_follow_tables_present() -> bool:
    """True when trader-follow tables exist on the mapped metadata.

    The live social model maps to ``follows`` (V22). Older provisional names are
    retained so alternate schemas still enable the fan-out path.
    """
    try:
        from app.db.base import Base

        names = set(Base.metadata.tables.keys())
        return bool(
            names
            & {"follows", "trader_follows", "user_follows", "social_follows"}
        )
    except Exception:  # noqa: BLE001
        return False


async def notify_followed_trader_trade(
    *,
    follower_user_id: UUID,
    trader_label: str,
    slug: str,
    side: str,
    shares: float,
    price: float,
    session=None,
) -> None:
    """Fan a followed trader's fill to a follower. Never raises."""
    try:
        from app.services.notification_service import create_notification_best_effort

        await create_notification_best_effort(
            user_id=follower_user_id,
            type="followed_trade",
            title=f"{trader_label} traded",
            body=(
                f"{trader_label} {side.upper()} {shares:g} on {slug} @ {price:.4f}"
            ),
            link=f"/markets/{slug}",
            session=session,
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify_followed_trader_trade failed", exc_info=True)


async def notify_followers_of_paper_trade(
    *,
    trader_user_id: UUID,
    slug: str,
    side: str,
    shares: float,
    price: float,
    session=None,
) -> None:
    """Notify every follower of ``trader_user_id`` about a paper fill.

    Additive observation hook — never raises into the producing transaction
    (same contract as ``notify_order_filled``).
    """
    if not social_follow_tables_present():
        return
    try:
        from sqlalchemy import select

        from app.db.models import Follow, User
        from app.services.analytics_leaderboard import anonymized_username

        async def _fanout(db) -> None:
            trader = await db.scalar(select(User).where(User.id == trader_user_id))
            if trader is None:
                return
            # Opted-out profiles stay off the social surface (feed + notify).
            if not getattr(trader, "profile_public", True):
                return
            trader_label = anonymized_username(
                trader.id, display_name=trader.display_name
            )
            follower_ids = (
                await db.scalars(
                    select(Follow.follower_id).where(
                        Follow.followee_id == trader_user_id
                    )
                )
            ).all()
            for follower_id in follower_ids:
                await notify_followed_trader_trade(
                    follower_user_id=follower_id,
                    trader_label=trader_label,
                    slug=slug,
                    side=side,
                    shares=shares,
                    price=price,
                    session=db,
                )

        if session is not None:
            await _fanout(session)
            return

        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as own:
            await _fanout(own)
            await own.commit()
    except Exception:  # noqa: BLE001
        logger.warning("notify_followers_of_paper_trade failed", exc_info=True)


# ---------------------------------------------------------------------------
# Loop V49 E2 — watchlist fans for forecast lock / market resolve
# ---------------------------------------------------------------------------

_FORECAST_LOCKED_TYPE = "forecast_locked"
_MARKET_RESOLVED_TYPE = "market_resolved"


async def catalog_slug_for_external_market(session, external_market) -> str | None:
    """Map an ExternalMarket to a catalog Market.slug used by watchlists.

    Bridged rows key on venue identity stored as ``Market.external_slug`` (and
    sometimes ``Market.external_id`` / ``Market.slug``). Returns None when no
    catalog row matches — no watchers can exist without a catalog slug.
    Never raises.
    """
    try:
        from sqlalchemy import func, or_, select

        from app.db.models import Market

        external_id = str(getattr(external_market, "external_id", "") or "").strip()
        if not external_id:
            return None
        lowered = external_id.lower()
        return await session.scalar(
            select(Market.slug)
            .where(
                or_(
                    Market.external_slug == external_id,
                    func.lower(Market.external_slug) == lowered,
                    Market.external_id == external_id,
                    func.lower(Market.external_id) == lowered,
                    Market.slug == external_id,
                    func.lower(Market.slug) == lowered,
                )
            )
            .limit(1)
        )
    except Exception:  # noqa: BLE001
        logger.warning("catalog_slug_for_external_market failed", exc_info=True)
        return None


async def _watchers_for_slug(session, slug: str) -> list[UUID]:
    from sqlalchemy import select

    from app.db.models import Watchlist

    rows = (
        await session.scalars(select(Watchlist.user_id).where(Watchlist.slug == slug))
    ).all()
    return list(rows)


async def _already_notified(
    session,
    *,
    user_id: UUID,
    ntype: str,
    link: str,
) -> bool:
    """Dedupe per (user, type, link) within 1h (V90 frozen contract)."""
    from app.services.notification_service import recent_duplicate

    existing = await recent_duplicate(
        session, user=user_id, type=ntype, link=link
    )
    return existing is not None


async def notify_watchers_forecast_locked(
    *,
    external_market,
    forecast=None,
    session=None,
) -> int:
    """Notify users watching this market that a forecast locked. Never raises.

    Returns the number of notifications created (0 on miss/dedupe/error).
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.notification_service import create_notification_best_effort

        async def _run(db) -> int:
            slug = await catalog_slug_for_external_market(db, external_market)
            if not slug:
                return 0
            watchers = await _watchers_for_slug(db, slug)
            if not watchers:
                return 0
            link = f"/markets/{slug}"
            title_label = (
                getattr(external_market, "title", None) or slug
            )
            prob = None
            if forecast is not None and getattr(forecast, "user_probability", None) is not None:
                try:
                    prob = float(forecast.user_probability)
                except (TypeError, ValueError):
                    prob = None
            body = f"Model forecast locked on {title_label}"
            if prob is not None:
                body = f"{body} (p={prob:.3f})"
            created = 0
            for user_id in watchers:
                if await _already_notified(
                    db,
                    user_id=user_id,
                    ntype=_FORECAST_LOCKED_TYPE,
                    link=link,
                ):
                    continue
                row = await create_notification_best_effort(
                    user_id=user_id,
                    type=_FORECAST_LOCKED_TYPE,
                    title=f"Forecast locked: {title_label}"[:200],
                    body=body,
                    link=link,
                    session=db,
                    idempotent=True,
                )
                if row is not None:
                    created += 1
            return created

        if session is not None:
            return await _run(session)

        async with AsyncSessionLocal() as own:
            n = await _run(own)
            if n:
                await own.commit()
            return n
    except Exception:  # noqa: BLE001
        logger.warning("notify_watchers_forecast_locked failed", exc_info=True)
        return 0


async def notify_scanner_fired(
    *,
    scanner,
    run,
    market_slug: str,
    title: str,
    session=None,
) -> int:
    """Insert in-app rows for scanner owner + subscribers. Never raises."""
    try:
        from sqlalchemy import select

        from app.db.models import Subscription
        from app.db.session import AsyncSessionLocal
        from app.services.notification_service import create_notification_idempotent

        async def _run(db) -> int:
            targets: list[str] = []
            owner = getattr(scanner, "owner", None)
            if owner:
                targets.append(str(owner))
            subs = (
                await db.scalars(
                    select(Subscription.user).where(
                        Subscription.ref_type == "scanner",
                        Subscription.ref_id == scanner.id,
                    )
                )
            ).all()
            for u in subs:
                key = str(u)
                if key not in targets:
                    targets.append(key)
            if not targets:
                return 0
            link = f"/scanners/{scanner.id}"
            body = f"{title} on {market_slug}"[:1000]
            created = 0
            for user_key in targets:
                row = await create_notification_idempotent(
                    db,
                    user=user_key,
                    type="scanner:fired",
                    title=str(title)[:200],
                    body=body,
                    link=link,
                )
                if row is not None:
                    created += 1
            return created

        if session is not None:
            return await _run(session)

        async with AsyncSessionLocal() as own:
            n = await _run(own)
            if n:
                await own.commit()
            return n
    except Exception:  # noqa: BLE001
        logger.warning("notify_scanner_fired failed", exc_info=True)
        return 0


async def notify_watchers_brief_created(
    *,
    market_slug: str,
    headline: str,
    brief_id: UUID | None = None,
    session=None,
) -> int:
    """Notify watchlist followers when an analyst brief is published. Never raises."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.notification_service import create_notification_idempotent

        async def _run(db) -> int:
            watchers = await _watchers_for_slug(db, market_slug)
            if not watchers:
                return 0
            link = f"/markets/{market_slug}"
            if brief_id is not None:
                link = f"/markets/{market_slug}?brief={brief_id}"
            created = 0
            for user_id in watchers:
                row = await create_notification_idempotent(
                    db,
                    user_id=user_id,
                    type="brief",
                    title=f"Brief: {headline}"[:200],
                    body=str(headline)[:1000],
                    link=link[:300],
                )
                if row is not None:
                    created += 1
            return created

        if session is not None:
            return await _run(session)

        async with AsyncSessionLocal() as own:
            n = await _run(own)
            if n:
                await own.commit()
            return n
    except Exception:  # noqa: BLE001
        logger.warning("notify_watchers_brief_created failed", exc_info=True)
        return 0


async def notify_watchers_market_resolved(
    *,
    external_market,
    session=None,
) -> int:
    """Notify users watching this market that it resolved. Never raises.

    Returns the number of notifications created (0 on miss/dedupe/error).
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.notification_service import create_notification_best_effort

        async def _run(db) -> int:
            slug = await catalog_slug_for_external_market(db, external_market)
            if not slug:
                return 0
            watchers = await _watchers_for_slug(db, slug)
            if not watchers:
                return 0
            link = f"/markets/{slug}"
            title_label = (
                getattr(external_market, "title", None) or slug
            )
            outcome = getattr(external_market, "winning_outcome", None)
            outcome_label = (
                "YES" if outcome == 1 else "NO" if outcome == 0 else str(outcome)
            )
            body = f"Market resolved {outcome_label}: {title_label}"
            created = 0
            for user_id in watchers:
                if await _already_notified(
                    db,
                    user_id=user_id,
                    ntype=_MARKET_RESOLVED_TYPE,
                    link=link,
                ):
                    continue
                row = await create_notification_best_effort(
                    user_id=user_id,
                    type=_MARKET_RESOLVED_TYPE,
                    title=f"Market resolved: {title_label}"[:256],
                    body=body,
                    link=link,
                    session=db,
                )
                if row is not None:
                    created += 1
            return created

        if session is not None:
            return await _run(session)

        async with AsyncSessionLocal() as own:
            n = await _run(own)
            if n:
                await own.commit()
            return n
    except Exception:  # noqa: BLE001
        logger.warning("notify_watchers_market_resolved failed", exc_info=True)
        return 0


async def mirror_alert_to_admin_notifications(
    *,
    alert_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> int:
    """Mirror drift/ops alerts into admin user inboxes. Returns rows created.

    Reuses the existing AlertDispatchService path — this is a secondary
    per-user mirror, not a parallel alert system. Never raises.
    """
    try:
        if not _is_admin_alert_type(alert_type):
            return 0
        emails = _admin_emails()
        if not emails:
            return 0

        from sqlalchemy import select

        from app.db.models import User
        from app.db.session import AsyncSessionLocal
        from app.services.notification_service import (
            _publish_new_notification,
            create_notification,
        )

        created = 0
        rows = []
        async with AsyncSessionLocal() as session:
            users = (
                await session.scalars(select(User).where(User.email.in_(emails)))
            ).all()
            for user in users:
                row = await create_notification(
                    session,
                    user_id=user.id,
                    type=alert_type[:24],
                    title=f"Ops: {alert_type}"[:200],
                    body=message,
                    link=(payload or {}).get("link"),
                )
                rows.append(row)
                created += 1
            if created:
                await session.commit()
        for row in rows:
            await _publish_new_notification(row)
        return created
    except Exception:  # noqa: BLE001
        logger.warning("mirror_alert_to_admin_notifications failed", exc_info=True)
        return 0
