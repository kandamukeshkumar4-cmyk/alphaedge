"""Portfolio equity snapshot math + persistence (Loop V15 B5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PortfolioEquitySnapshot, User


async def compute_user_equity(
    session: AsyncSession, user: User
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (cash, positions_mtm, equity) using portfolio mark-to-market helpers."""
    from app.api.v1.portfolio import (
        _enrich_live_pnl,
        _latest_implied_yes_by_slug,
        _load_paper_orders,
    )

    cash = Decimal(str(user.paper_balance))
    positions = await _load_paper_orders(session, user.id.hex)
    open_positions = [p for p in positions if not p.settled]
    slugs = list({p.market_slug for p in open_positions})
    implied = await _latest_implied_yes_by_slug(session, slugs)
    _unrealized, portfolio_value = _enrich_live_pnl(
        list(open_positions), implied, float(cash)
    )
    equity = Decimal(str(round(portfolio_value, 4)))
    positions_mtm = Decimal(str(round(float(equity - cash), 4)))
    return cash, positions_mtm, equity


async def snapshot_user_equity(
    session: AsyncSession,
    user: User,
    *,
    snapshot_date: date | None = None,
) -> PortfolioEquitySnapshot | None:
    """Insert today's equity row; return None if already present (idempotent)."""
    day = snapshot_date or datetime.now(UTC).date()
    existing = await session.scalar(
        select(PortfolioEquitySnapshot).where(
            PortfolioEquitySnapshot.user_id == user.id,
            PortfolioEquitySnapshot.snapshot_date == day,
        )
    )
    if existing is not None:
        return None
    cash, mtm, equity = await compute_user_equity(session, user)
    row = PortfolioEquitySnapshot(
        user_id=user.id,
        snapshot_date=day,
        cash_balance=cash,
        positions_mtm=mtm,
        equity=equity,
    )
    session.add(row)
    await session.flush()
    return row


async def snapshot_all_users(
    session: AsyncSession,
    *,
    snapshot_date: date | None = None,
) -> dict[str, int | str]:
    day = snapshot_date or datetime.now(UTC).date()
    users = (await session.scalars(select(User))).all()
    created = 0
    skipped = 0
    for user in users:
        row = await snapshot_user_equity(session, user, snapshot_date=day)
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
