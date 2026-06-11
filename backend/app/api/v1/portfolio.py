from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import OddsSnapshot, User
from app.db.session import get_db
from app.schemas.portfolio import (
    PORTFOLIO_DISCLAIMER,
    PortfolioPositionResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
)

router = APIRouter(prefix="/api/v1", tags=["portfolio"])


async def _latest_implied_yes_by_slug(
    db: AsyncSession,
    slugs: list[str],
) -> dict[str, float]:
    if not slugs:
        return {}

    latest_subq = (
        select(
            OddsSnapshot.market_slug,
            func.max(OddsSnapshot.captured_at).label("max_at"),
        )
        .where(OddsSnapshot.market_slug.in_(slugs))
        .group_by(OddsSnapshot.market_slug)
        .subquery()
    )
    rows = (
        await db.execute(
            select(OddsSnapshot.market_slug, OddsSnapshot.implied_yes).join(
                latest_subq,
                (OddsSnapshot.market_slug == latest_subq.c.market_slug)
                & (OddsSnapshot.captured_at == latest_subq.c.max_at),
            )
        )
    ).all()
    return {slug: float(implied) for slug, implied in rows}


def _enrich_live_pnl(
    positions: list[PortfolioPositionResponse],
    implied_by_slug: dict[str, float],
    paper_balance: float,
) -> tuple[float, float]:
    unrealized_total = 0.0
    mark_to_market = 0.0

    for pos in positions:
        if pos.settled:
            pos.current_price = None
            pos.unrealized_pnl = 0.0
            pos.pnl_pct = 0.0
            continue

        implied_yes = implied_by_slug.get(pos.market_slug, pos.avg_cost)
        outcome = pos.outcome.lower()
        if outcome == "yes":
            current_price = implied_yes
            unrealized = pos.shares * (current_price - pos.avg_cost)
            mark_to_market += pos.shares * current_price
        else:
            current_price = round(1.0 - implied_yes, 4)
            unrealized = pos.shares * (current_price - pos.avg_cost)
            mark_to_market += pos.shares * current_price

        pos.current_price = round(current_price, 4)
        pos.unrealized_pnl = round(unrealized, 4)
        pos.pnl_pct = round(unrealized / pos.cost, 4) if pos.cost > 0 else 0.0
        unrealized_total += pos.unrealized_pnl

    portfolio_value = round(paper_balance + mark_to_market, 4)
    return round(unrealized_total, 4), portfolio_value


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
                   MAX(CASE WHEN po.settled THEN 1 ELSE 0 END) AS settled,
                   SUM(
                     CASE WHEN po.settled AND UPPER(po.outcome)=COALESCE(mr.outcome,'')
                          THEN po.shares*1.0 - po.cost
                          WHEN po.settled THEN 0.0 - po.cost
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
                settled=bool(row["settled"]),
            )
        )
    return positions


@router.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioSummaryResponse:
    positions: list[PortfolioPositionResponse] = []
    try:
        positions = await _load_paper_orders(db, current_user.id.hex)
    except (OperationalError, ProgrammingError):
        positions = []

    paper_balance = float(current_user.paper_balance)
    open_positions = [p for p in positions if not p.settled]
    slugs = list({pos.market_slug for pos in open_positions})
    implied_by_slug = await _latest_implied_yes_by_slug(db, slugs)
    unrealized_pnl, _ = _enrich_live_pnl(list(open_positions), implied_by_slug, paper_balance)

    total_invested = sum(pos.cost for pos in open_positions)
    return PortfolioSummaryResponse(
        bankroll=paper_balance,
        open_positions=len(open_positions),
        total_invested=round(total_invested, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        unrealized_pnl_pct=round(
            unrealized_pnl / total_invested * 100 if total_invested > 0 else 0.0,
            2,
        ),
    )


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    positions: list[PortfolioPositionResponse] = []
    total_trades = 0

    try:
        positions = await _load_paper_orders(db, current_user.id.hex)
        total_trades = len(positions)
    except (OperationalError, ProgrammingError):
        positions = []
        total_trades = 0

    realized_pnl = sum(
        pos.realized_pnl for pos in positions if pos.realized_pnl is not None
    )

    paper_balance = float(current_user.paper_balance)
    slugs = list({pos.market_slug for pos in positions if not pos.settled})
    implied_by_slug = await _latest_implied_yes_by_slug(db, slugs)
    unrealized_pnl, portfolio_value = _enrich_live_pnl(
        positions,
        implied_by_slug,
        paper_balance,
    )

    return PortfolioResponse(
        paper_balance=paper_balance,
        positions=positions,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        portfolio_value=portfolio_value,
        total_trades=total_trades,
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )
