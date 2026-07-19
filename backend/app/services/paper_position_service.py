"""Aggregate a user's open paper position for one market outcome.

BUY rows add FIFO lots and SELL rows consume the oldest lots.  Keeping the
remaining lots (rather than averaging every BUY row) prevents a fully closed
cycle from diluting the cost basis of a later re-opened position.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaperOrder


@dataclass(frozen=True)
class OpenPaperPosition:
    net_shares: Decimal
    avg_cost: Decimal  # Decimal("0") when no BUY rows exist

    @property
    def open_cost_basis(self) -> Decimal:
        return self.net_shares * self.avg_cost


def fifo_open_position(orders: Iterable[PaperOrder]) -> OpenPaperPosition:
    """Return the remaining FIFO BUY lots after applying SELL rows.

    ``PaperOrder.cost`` is the total row cost, so each BUY lot stores its
    per-share cost.  SELL rows consume lots in creation order and never add a
    new cost basis.  Invalid over-sells are exhausted at zero rather than
    creating a negative open position; valid order paths never over-sell.
    """
    lots: list[list[Decimal]] = []
    for order in orders:
        shares = Decimal(str(order.shares))
        if shares <= 0:
            continue
        action = getattr(order.action, "value", order.action)
        if str(action).upper() == "SELL":
            remaining = shares
            while remaining > 0 and lots:
                lot = lots[0]
                consumed = min(remaining, lot[0])
                lot[0] -= consumed
                remaining -= consumed
                if lot[0] <= 0:
                    lots.pop(0)
            continue

        unit_cost = Decimal(str(order.cost)) / shares
        lots.append([shares, unit_cost])

    net_shares = sum((lot[0] for lot in lots), Decimal("0"))
    open_cost_basis = sum((lot[0] * lot[1] for lot in lots), Decimal("0"))
    avg_cost = open_cost_basis / net_shares if net_shares > 0 else Decimal("0")
    return OpenPaperPosition(net_shares=net_shares, avg_cost=avg_cost)


async def get_open_paper_position(
    db: AsyncSession,
    user_id: UUID,
    slug: str,
    outcome: str,
) -> OpenPaperPosition:
    statement = select(PaperOrder).where(
        PaperOrder.user_id == user_id,
        PaperOrder.slug == slug,
        PaperOrder.outcome == outcome,
        PaperOrder.settled.is_(False),
    )
    statement = statement.order_by(PaperOrder.created_at.asc(), PaperOrder.id.asc())
    orders = (await db.scalars(statement)).all()
    return fifo_open_position(orders)
