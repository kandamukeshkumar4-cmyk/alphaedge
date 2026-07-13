"""Bounded GTD order-expiry sweep using the canonical cancellation path."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRun, Order, OrderStatus
from app.services.order_book_service import (
    OrderBookService,
    OrderStateConflictError,
)

ORDER_EXPIRY_JOB_NAME = "order_expiry_task"
DEFAULT_EXPIRY_BATCH_SIZE = 100
MAX_EXPIRY_BATCH_SIZE = 500


async def sweep_expired_orders(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_EXPIRY_BATCH_SIZE,
) -> dict[str, int]:
    """Cancel at most *limit* expired resting orders through A3's service path."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    bounded_limit = min(max(limit, 1), MAX_EXPIRY_BATCH_SIZE)
    rows = (
        await session.execute(
            select(Order.id, Order.account_id)
            .where(
                Order.status.in_((OrderStatus.OPEN, OrderStatus.PARTIAL)),
                Order.expires_at.is_not(None),
                Order.expires_at <= now,
            )
            .order_by(Order.expires_at, Order.id)
            .limit(bounded_limit)
            .with_for_update(skip_locked=True)
        )
    ).all()

    service = OrderBookService(session)
    expired = 0
    skipped = 0
    for order_id, account_id in rows:
        try:
            await service.cancel_order(order_id, account_id)
            expired += 1
        except OrderStateConflictError:
            skipped += 1

    return {"scanned": len(rows), "expired": expired, "skipped": skipped}


async def order_expiry_task(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ entrypoint with a durable JobRun heartbeat for every invocation."""
    from app.db.session import AsyncSessionLocal

    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    now = ctx.get("now")
    limit = int(ctx.get("limit", DEFAULT_EXPIRY_BATCH_SIZE))
    async with session_factory() as session:
        try:
            summary = await sweep_expired_orders(session, now=now, limit=limit)
            session.add(
                JobRun(
                    job_name=ORDER_EXPIRY_JOB_NAME,
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
                    job_name=ORDER_EXPIRY_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
