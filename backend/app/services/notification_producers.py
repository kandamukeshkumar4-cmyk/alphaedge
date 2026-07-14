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
    """True when V22 (or later) trader-follow tables exist on the mapped metadata."""
    try:
        from app.db.base import Base

        names = set(Base.metadata.tables.keys())
        return bool(names & {"trader_follows", "user_follows", "social_follows"})
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
) -> None:
    """Fan a followed trader's fill to a follower. No-ops if social tables absent."""
    if not social_follow_tables_present():
        return
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
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify_followed_trader_trade failed", exc_info=True)


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
        from app.services.notification_service import create_notification

        created = 0
        async with AsyncSessionLocal() as session:
            users = (
                await session.scalars(select(User).where(User.email.in_(emails)))
            ).all()
            for user in users:
                await create_notification(
                    session,
                    user_id=user.id,
                    type=alert_type[:64],
                    title=f"Ops: {alert_type}",
                    body=message,
                    link=(payload or {}).get("link"),
                )
                created += 1
            if created:
                await session.commit()
        return created
    except Exception:  # noqa: BLE001
        logger.warning("mirror_alert_to_admin_notifications failed", exc_info=True)
        return 0
