"""Aggregate a user's open paper position for one market outcome.

BUY rows add shares; SELL rows subtract. Average cost is computed from BUY
rows only (sells realize P&L against that average, they do not change it).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaperOrder


@dataclass(frozen=True)
class OpenPaperPosition:
    net_shares: Decimal
    avg_cost: Decimal  # Decimal("0") when no BUY rows exist


async def get_open_paper_position(
    db: AsyncSession,
    user_id: UUID,
    slug: str,
    outcome: str,
) -> OpenPaperPosition:
    row = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (PaperOrder.action == "SELL", -PaperOrder.shares),
                            else_=PaperOrder.shares,
                        )
                    ),
                    0,
                ).label("net_shares"),
                func.coalesce(
                    func.sum(
                        case((PaperOrder.action == "BUY", PaperOrder.cost), else_=0)
                    ),
                    0,
                ).label("buy_cost"),
                func.coalesce(
                    func.sum(
                        case((PaperOrder.action == "BUY", PaperOrder.shares), else_=0)
                    ),
                    0,
                ).label("buy_shares"),
            ).where(
                PaperOrder.user_id == user_id,
                PaperOrder.slug == slug,
                PaperOrder.outcome == outcome,
                PaperOrder.settled.is_(False),
            )
        )
    ).one()
    net_shares = Decimal(str(row.net_shares))
    buy_shares = Decimal(str(row.buy_shares))
    buy_cost = Decimal(str(row.buy_cost))
    open_cost_basis = (
        buy_cost * (net_shares / buy_shares)
        if buy_shares > 0 and net_shares > 0
        else Decimal("0")
    )
    avg_cost = open_cost_basis / net_shares if net_shares > 0 else Decimal("0")
    return OpenPaperPosition(net_shares=net_shares, avg_cost=avg_cost)
