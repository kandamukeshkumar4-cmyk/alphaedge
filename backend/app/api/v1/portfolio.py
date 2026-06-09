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
            SELECT slug, side,
                   SUM(shares) AS shares,
                   AVG(price)  AS avg_cost,
                   SUM(cost)   AS cost
            FROM paper_orders
            WHERE user_id = :user_id
            GROUP BY slug, side
            ORDER BY MAX(created_at) DESC
            """
        ),
        {"user_id": user_id},
    )
    rows = result.mappings().all()
    positions: list[PortfolioPositionResponse] = []
    for row in rows:
        positions.append(
            PortfolioPositionResponse(
                id=None,
                market_slug=str(row["slug"]),
                side=str(row["side"]),
                shares=float(row["shares"]),
                avg_cost=float(row["avg_cost"]),
                cost=float(row["cost"]),
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
        positions = await _load_paper_orders(db, str(current_user.id))
        total_trades = len(positions)
    except (OperationalError, ProgrammingError):
        positions = []
        total_trades = 0

    return PortfolioResponse(
        paper_balance=float(current_user.paper_balance),
        positions=positions,
        realized_pnl=0.0,
        total_trades=total_trades,
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )
