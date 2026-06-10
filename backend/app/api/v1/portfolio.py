from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.portfolio import (
    PORTFOLIO_DISCLAIMER,
    PortfolioPositionResponse,
    PortfolioResponse,
)

router = APIRouter(prefix="/api/v1", tags=["portfolio"])


async def _load_paper_orders(
    db: AsyncSession,
    user_id: str,
) -> list[PortfolioPositionResponse]:
    result = await db.execute(
        text(
            """
            SELECT po.slug, po.side, po.outcome,
                   COALESCE(m.title, po.slug) AS market_title,
                   SUM(po.shares)             AS shares,
                   AVG(po.price)              AS avg_cost,
                   SUM(po.cost)               AS cost,
                   SUM(
                     CASE WHEN po.settled=1 AND UPPER(po.outcome)=COALESCE(mr.outcome,'')
                          THEN po.shares*1.0 - po.cost
                          WHEN po.settled=1 THEN 0.0 - po.cost
                          ELSE 0.0 END
                   ) AS realized_pnl
            FROM paper_orders po
            LEFT JOIN markets m ON m.slug=po.slug
            LEFT JOIN market_resolutions mr ON mr.slug=po.slug
            WHERE po.user_id=:user_id
            GROUP BY po.slug, po.side, po.outcome
            ORDER BY MAX(po.created_at) DESC
            """
        ),
        {"user_id": user_id},
    )
    rows = result.mappings().all()
    positions: list[PortfolioPositionResponse] = []
    for row in rows:
        slug = str(row["slug"])
        side = str(row["side"])
        outcome = str(row["outcome"])
        positions.append(
            PortfolioPositionResponse(
                id=f"{slug}:{side}:{outcome}",
                market_slug=slug,
                side=side,
                outcome=outcome,
                market_title=str(row["market_title"]),
                shares=float(row["shares"]),
                avg_cost=float(row["avg_cost"]),
                cost=float(row["cost"]),
                realized_pnl=float(row["realized_pnl"]),
            )
        )
    return positions


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    positions: list[PortfolioPositionResponse] = []
    total_trades = 0

    try:
        # current_user.id is a UUID; SQLite stores UUIDs as 32-char hex
        # strings (CHAR(32), no dashes), so we pass .hex for the text() query.
        positions = await _load_paper_orders(db, current_user.id.hex)
        total_trades = len(positions)
    except (OperationalError, ProgrammingError):
        positions = []
        total_trades = 0

    realized_pnl = sum(
        pos.realized_pnl for pos in positions if pos.realized_pnl is not None
    )

    return PortfolioResponse(
        paper_balance=float(current_user.paper_balance),
        positions=positions,
        realized_pnl=realized_pnl,
        total_trades=total_trades,
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )
