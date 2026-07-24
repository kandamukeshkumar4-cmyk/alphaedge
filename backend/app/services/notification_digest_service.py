"""Loop V90 N4 — daily notification email digest (paper research only).

Composes unread notifications + today's fired alerts into plain text and
sends via ``scanner_email_service.send_plain_text_email`` when SMTP is
configured. Never places orders.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, NotificationPreference, SignalEvent, User
from app.services.scanner_alert_service import SCANNER_FIRED_SIGNAL_TYPE
from app.services.scanner_email_service import PAPER_FOOTER, send_plain_text_email, smtp_configured

logger = logging.getLogger(__name__)


def _day_start(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def _users_wanting_digest(session: AsyncSession) -> list[User]:
    """Users with email_digest=true (missing prefs row ⇒ default True)."""
    users = list((await session.scalars(select(User))).all())
    if not users:
        return []
    prefs = {
        p.user: p
        for p in (
            await session.scalars(select(NotificationPreference))
        ).all()
    }
    out: list[User] = []
    for user in users:
        pref = prefs.get(str(user.id))
        if pref is None or pref.email_digest:
            out.append(user)
    return out


async def _unread_for_user(session: AsyncSession, user_key: str) -> list[Notification]:
    return list(
        (
            await session.scalars(
                select(Notification)
                .where(
                    Notification.user == user_key,
                    Notification.read.is_(False),
                )
                .order_by(Notification.created_at.desc())
                .limit(50)
            )
        ).all()
    )


async def _todays_fired_alerts(
    session: AsyncSession, *, day_start: datetime
) -> list[SignalEvent]:
    return list(
        (
            await session.scalars(
                select(SignalEvent)
                .where(
                    SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE,
                    SignalEvent.created_at >= day_start,
                )
                .order_by(SignalEvent.created_at.desc())
                .limit(50)
            )
        ).all()
    )


def compose_digest_body(
    *,
    unread: list[Notification],
    fired: list[SignalEvent],
) -> str:
    lines = ["AlphaEdge daily digest", ""]
    lines.append(f"Unread notifications ({len(unread)}):")
    if unread:
        for row in unread:
            lines.append(f"- [{row.type}] {row.title}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append(f"Today's fired alerts ({len(fired)}):")
    if fired:
        for ev in fired:
            payload = ev.payload if isinstance(ev.payload, dict) else {}
            title = str(payload.get("title") or ev.market_id or "scanner:fired")
            lines.append(f"- {title}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append(PAPER_FOOTER)
    return "\n".join(lines)


async def run_notification_digest(
    session: AsyncSession,
    *,
    settings=None,
    smtp_factory=None,
    now: datetime | None = None,
    send_fn=None,
) -> dict[str, Any]:
    """Send digests for opted-in users. Skips silently when SMTP is off."""
    from app.core.config import get_settings

    settings = settings or get_settings()
    current = now or datetime.now(UTC)
    sender = send_fn or send_plain_text_email

    # Injected send_fn (tests) bypasses SMTP probe; production skips when unset.
    if send_fn is None and not smtp_configured(settings):
        return {
            "skipped": True,
            "reason": "smtp_unconfigured",
            "sent": 0,
            "candidates": 0,
        }

    users = await _users_wanting_digest(session)
    day_start = _day_start(current)
    fired = await _todays_fired_alerts(session, day_start=day_start)
    sent = 0
    for user in users:
        if not (user.email or "").strip():
            continue
        unread = await _unread_for_user(session, str(user.id))
        if not unread and not fired:
            continue
        body = compose_digest_body(unread=unread, fired=fired)
        ok = sender(
            to_addr=user.email,
            subject="AlphaEdge daily digest — paper research only",
            body=body,
            settings=settings,
            smtp_factory=smtp_factory,
        )
        if ok:
            sent += 1
    return {
        "skipped": False,
        "sent": sent,
        "candidates": len(users),
        "fired_alerts": len(fired),
        "date": day_start.date().isoformat(),
        "paper_trading_only": True,
    }
