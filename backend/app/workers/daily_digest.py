"""Loop V24 N3 — daily per-user in-app digest worker.

Once per user per day (idempotent), summarize:
* portfolio cash / equity change (when equity snapshots exist)
* positions resolved (paper orders marked settled)
* top market moves among the user's watchlist

Stores the result as a Notification with type=digest. In-app only — no email.

Wired both as ARQ registration (workers/tasks.py) AND as an in-process
flag-gated loop in main.py (prod runs uvicorn only).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    JobRun,
    Notification,
    OddsSnapshot,
    PaperOrder,
    PortfolioEquitySnapshot,
    User,
    Watchlist,
)
from app.services.notification_service import create_notification

DAILY_DIGEST_JOB_NAME = "daily_digest_task"
DIGEST_TYPE = "digest"


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


async def _already_digested(
    session: AsyncSession, user_id: UUID, day: date
) -> bool:
    start, end = _day_bounds(day)
    existing = await session.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == DIGEST_TYPE,
            Notification.created_at >= start,
            Notification.created_at < end,
        ).limit(1)
    )
    return existing is not None


async def _portfolio_line(
    session: AsyncSession, user: User, day: date
) -> str:
    """Describe portfolio change using equity snapshots when available."""
    cash = Decimal(str(user.paper_balance or 0))
    today_snap = await session.scalar(
        select(PortfolioEquitySnapshot).where(
            PortfolioEquitySnapshot.user_id == user.id,
            PortfolioEquitySnapshot.snapshot_date == day,
        )
    )
    prev_day = day - timedelta(days=1)
    prev_snap = await session.scalar(
        select(PortfolioEquitySnapshot).where(
            PortfolioEquitySnapshot.user_id == user.id,
            PortfolioEquitySnapshot.snapshot_date == prev_day,
        )
    )
    if today_snap is not None and prev_snap is not None:
        delta = Decimal(str(today_snap.equity)) - Decimal(str(prev_snap.equity))
        sign = "+" if delta >= 0 else ""
        return (
            f"Portfolio equity {float(today_snap.equity):.2f} "
            f"({sign}{float(delta):.2f} vs prior day); cash {float(cash):.2f}."
        )
    if today_snap is not None:
        return (
            f"Portfolio equity {float(today_snap.equity):.2f}; "
            f"cash {float(cash):.2f}."
        )
    return f"Paper cash balance {float(cash):.2f}."


async def _resolved_line(session: AsyncSession, user_id: UUID) -> str:
    settled = (
        await session.scalars(
            select(PaperOrder).where(
                PaperOrder.user_id == user_id,
                PaperOrder.settled.is_(True),
            )
        )
    ).all()
    if not settled:
        return "No resolved positions."
    # Prefer recently settled if realized_pnl present; otherwise count all settled.
    with_pnl = [o for o in settled if o.realized_pnl is not None]
    sample = with_pnl[-5:] if with_pnl else settled[-5:]
    total_pnl = sum((Decimal(str(o.realized_pnl or 0)) for o in with_pnl), Decimal("0"))
    slugs = ", ".join(o.slug for o in sample[:3])
    return (
        f"{len(settled)} settled position(s)"
        + (f" (realized PnL {float(total_pnl):+.2f})" if with_pnl else "")
        + (f": {slugs}" if slugs else "")
        + "."
    )


async def _watchlist_moves_line(session: AsyncSession, user_id: UUID) -> str:
    slugs = list(
        (
            await session.scalars(
                select(Watchlist.slug).where(Watchlist.user_id == user_id)
            )
        ).all()
    )
    if not slugs:
        return "Watchlist empty — no market moves to report."

    moves: list[tuple[str, float]] = []
    for slug in slugs:
        rows = (
            await session.execute(
                select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
                .where(OddsSnapshot.market_slug == slug)
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(2)
            )
        ).all()
        if len(rows) < 2:
            continue
        newest = float(rows[0][0])
        older = float(rows[1][0])
        moves.append((slug, newest - older))

    if not moves:
        return f"Watchlist ({len(slugs)} markets) — insufficient price history for moves."

    moves.sort(key=lambda x: abs(x[1]), reverse=True)
    top = moves[:3]
    parts = [f"{s} {d:+.3f}" for s, d in top]
    return "Top watchlist moves: " + "; ".join(parts) + "."


async def build_digest_for_user(
    session: AsyncSession,
    user: User,
    *,
    day: date | None = None,
) -> Notification | None:
    """Create today's digest notification for one user, or None if already done."""
    day = day or datetime.now(UTC).date()
    if await _already_digested(session, user.id, day):
        return None

    portfolio = await _portfolio_line(session, user, day)
    resolved = await _resolved_line(session, user.id)
    moves = await _watchlist_moves_line(session, user.id)
    body = "\n".join([portfolio, resolved, moves])
    title = f"Daily digest — {day.isoformat()}"
    return await create_notification(
        session,
        user_id=user.id,
        type=DIGEST_TYPE,
        title=title,
        body=body,
        link="/portfolio",
    )


async def run_daily_digest(
    session: AsyncSession,
    *,
    day: date | None = None,
) -> dict[str, Any]:
    """Run digest for all users. Idempotent per user per day."""
    day = day or datetime.now(UTC).date()
    users = list((await session.scalars(select(User))).all())
    created = 0
    skipped = 0
    for user in users:
        row = await build_digest_for_user(session, user, day=day)
        if row is None:
            skipped += 1
        else:
            created += 1
    return {
        "users": len(users),
        "created": created,
        "skipped": skipped,
        "date": day.isoformat(),
    }


async def daily_digest_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint (+ in-process loop caller)."""
    from app.db.session import AsyncSessionLocal

    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    day = ctx.get("digest_date")
    async with session_factory() as session:
        try:
            summary = await run_daily_digest(session, day=day)
            session.add(
                JobRun(
                    job_name=DAILY_DIGEST_JOB_NAME,
                    status="success",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            return summary
        except Exception as exc:
            await session.rollback()
            session.add(
                JobRun(
                    job_name=DAILY_DIGEST_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
