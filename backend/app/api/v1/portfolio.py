from decimal import Decimal

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
            SELECT
                id,
                market_slug,
                market_title,
                side,
                outcome,
                quantity,
                price,
                realized_pnl
            FROM paper_orders
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            """
        ),
        {"user_id": user_id},
    )
    rows = result.mappings().all()
    positions: list[PortfolioPositionResponse] = []
    for row in rows:
        positions.append(
            PortfolioPositionResponse(
                id=str(row["id"]),
                market_slug=str(row["market_slug"]),
                market_title=str(row["market_title"]),
                side=str(row["side"]),
                outcome=str(row["outcome"]),
                quantity=float(row["quantity"]),
                price=float(row["price"]) if row["price"] is not None else None,
                realized_pnl=(
                    float(row["realized_pnl"]) if row["realized_pnl"] is not None else None
                ),
            )
        )
    return positions


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    positions: list[PortfolioPositionResponse] = []
    realized_pnl = Decimal("0")
    total_trades = 0

    try:
        positions = await _load_paper_orders(db, str(current_user.id))
        total_trades = len(positions)
        for position in positions:
            if position.realized_pnl is not None:
                realized_pnl += Decimal(str(position.realized_pnl))
    except (OperationalError, ProgrammingError):
        positions = []
        realized_pnl = Decimal("0")
        total_trades = 0

    return PortfolioResponse(
        paper_balance=float(current_user.paper_balance),
        positions=positions,
        realized_pnl=float(realized_pnl),
        total_trades=total_trades,
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )
