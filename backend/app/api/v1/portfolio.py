from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import (
    Market,
    MarketResolution,
    OddsSnapshot,
    PaperOrder,
    PortfolioEquitySnapshot,
    User,
)
from app.db.session import get_db
from app.schemas.portfolio import (
    PORTFOLIO_DISCLAIMER,
    AttributionTradeResponse,
    EquityCurvePoint,
    EquityCurveResponse,
    ExposureGroupResponse,
    ExposureResponse,
    PortfolioAttributionResponse,
    PortfolioPositionResponse,
    PortfolioResponse,
    PortfolioRiskResponse,
    PortfolioSummaryResponse,
)
from app.services.analytics_attribution import (
    OrderLeg,
    attributed_trades,
    compute_attribution,
)
from app.services.exposure_service import PositionInput, compute_exposure
from app.services.portfolio_risk import ClosedTrade, OpenExposure, compute_risk_metrics

import logging

logger = logging.getLogger(__name__)


def _portfolio_unavailable() -> HTTPException:
    """Audit H-REL-01: a transient DB failure must NOT look like a wiped
    portfolio ($0 / no positions). Surface it as 503 so the UI can show
    'temporarily unavailable' instead of empty-as-success."""
    logger.exception("portfolio query failed — returning 503 (was silently swallowed)")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Portfolio temporarily unavailable",
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
                   -- MAX() because m.title is not in GROUP BY: SQLite tolerates the
                   -- bare column but PostgreSQL raises GroupingError, which the
                   -- caller's except used to swallow into "0 positions" (real bug).
                   COALESCE(MAX(m.title), po.slug) AS market_title,
                   SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) AS shares,
                   CASE WHEN SUM(CASE WHEN po.action='BUY' THEN po.shares ELSE 0 END) > 0
                        THEN CAST(SUM(CASE WHEN po.action='BUY' THEN po.cost ELSE 0 END) AS REAL)
                             / CAST(SUM(CASE WHEN po.action='BUY' THEN po.shares ELSE 0 END) AS REAL)
                        ELSE 0 END                                                    AS avg_cost,
                   SUM(CASE WHEN po.action='SELL' THEN -po.cost ELSE po.cost END)     AS cost,
                   MAX(CASE WHEN po.settled THEN 1 ELSE 0 END) AS settled,
                   SUM(COALESCE(po.realized_pnl, 0.0)) +
                   CASE
                     WHEN MAX(CASE WHEN po.settled THEN 1 ELSE 0 END) = 1
                          AND SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) > 0
                          AND UPPER(po.outcome) = COALESCE(MAX(mr.outcome),'')
                     THEN CAST(SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) AS REAL)
                          - CAST(SUM(CASE WHEN po.action='BUY' THEN po.cost ELSE 0 END) AS REAL)
                            * CAST(SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) AS REAL)
                            / NULLIF(CAST(SUM(CASE WHEN po.action='BUY' THEN po.shares ELSE 0 END) AS REAL), 0)
                     WHEN MAX(CASE WHEN po.settled THEN 1 ELSE 0 END) = 1
                          AND SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) > 0
                     THEN 0.0 - CAST(SUM(CASE WHEN po.action='BUY' THEN po.cost ELSE 0 END) AS REAL)
                                * CAST(SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) AS REAL)
                                / NULLIF(CAST(SUM(CASE WHEN po.action='BUY' THEN po.shares ELSE 0 END) AS REAL), 0)
                     ELSE 0.0
                   END                                                             AS realized_pnl
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
        shares = float(row["shares"])
        settled = bool(row["settled"])
        if shares <= 0 and not settled:
            settled = True
        positions.append(
            PortfolioPositionResponse(
                id=f"{slug}:{side}:{outcome}",
                market_slug=slug,
                side=side,
                outcome=outcome,
                market_title=str(row["market_title"]),
                shares=max(shares, 0.0),
                avg_cost=float(row["avg_cost"]),
                cost=max(float(row["cost"]), 0.0),
                realized_pnl=float(row["realized_pnl"]),
                settled=settled,
            )
        )
    return positions


@router.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioSummaryResponse:
    try:
        positions = await _load_paper_orders(db, current_user.id.hex)
    except (OperationalError, ProgrammingError) as exc:
        raise _portfolio_unavailable() from exc

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


@router.get("/portfolio/risk", response_model=PortfolioRiskResponse)
async def get_portfolio_risk(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioRiskResponse:
    """Risk metrics over the user's paper book (E12): win rate, drawdown,
    per-trade Sharpe, and open exposure by market category."""
    try:
        positions = await _load_paper_orders(db, current_user.id.hex)
    except (OperationalError, ProgrammingError) as exc:
        raise _portfolio_unavailable() from exc

    # Only settled trades with a positive cost basis are usable: a fully
    # round-tripped-to-flat position has its net cost clamped to 0 upstream and
    # cannot yield a per-trade return, so it must be excluded from ALL closed
    # metrics (win_rate, drawdown, Sharpe) — not just Sharpe — to keep every
    # metric describing the same trade population.
    closed = [
        ClosedTrade(cost=p.cost, realized_pnl=p.realized_pnl or 0.0)
        for p in positions
        if p.settled and p.cost > 0
    ]
    open_positions = [p for p in positions if not p.settled]

    categories: dict[str, str] = {}
    open_slugs = list({p.market_slug for p in open_positions})
    if open_slugs:
        rows = (
            await db.execute(
                select(Market.slug, Market.category).where(Market.slug.in_(open_slugs))
            )
        ).all()
        categories = {str(slug): str(cat or "Other") for slug, cat in rows}

    exposures = [
        OpenExposure(category=categories.get(p.market_slug, "Other"), cost=p.cost)
        for p in open_positions
        if p.cost > 0
    ]

    metrics = compute_risk_metrics(closed, exposures)
    return PortfolioRiskResponse(
        n_closed=metrics.n_closed,
        total_realized_pnl=metrics.total_realized_pnl,
        win_rate=metrics.win_rate,
        max_drawdown=metrics.max_drawdown,
        sharpe=metrics.sharpe,
        exposure_by_category=metrics.exposure_by_category,
        exposure_pct_by_category=metrics.exposure_pct_by_category,
    )


def _trade_to_response(t) -> AttributionTradeResponse:
    return AttributionTradeResponse(
        order_id=t.order_id,
        slug=t.slug,
        title=t.title,
        category=t.category,
        side=t.side,
        cost=t.cost,
        realized_pnl=t.realized_pnl,
        created_at=t.created_at.isoformat(),
    )


@router.get("/portfolio/attribution", response_model=PortfolioAttributionResponse)
async def get_portfolio_attribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    top_n: int = 5,
) -> PortfolioAttributionResponse:
    """B2 — top/bottom trades, ROI, monthly + category P&L (paper only).

    Uses double-count-safe attribution math (SELL realized_pnl XOR settlement
    on remaining shares) — not the E12 grouped ``_load_paper_orders`` formula.
    """
    top_n = min(max(int(top_n), 1), 20)
    try:
        orders = (
            await db.scalars(
                select(PaperOrder).where(PaperOrder.user_id == current_user.id)
            )
        ).all()
    except (OperationalError, ProgrammingError) as exc:
        raise _portfolio_unavailable() from exc

    slugs = list({o.slug for o in orders})
    categories: dict[str, str] = {}
    titles: dict[str, str] = {}
    resolutions: dict[str, str] = {}
    if slugs:
        market_rows = (
            await db.execute(
                select(Market.slug, Market.category, Market.title).where(
                    Market.slug.in_(slugs)
                )
            )
        ).all()
        categories = {str(s): str(c or "Other") for s, c, _ in market_rows}
        titles = {str(s): str(t or s) for s, _, t in market_rows}
        res_rows = (
            await db.execute(
                select(MarketResolution.slug, MarketResolution.outcome).where(
                    MarketResolution.slug.in_(slugs)
                )
            )
        ).all()
        resolutions = {str(s): str(o) for s, o in res_rows}

    legs = [
        OrderLeg(
            id=str(o.id),
            slug=o.slug,
            outcome=o.outcome,
            action=o.action,
            shares=float(o.shares),
            cost=float(o.cost),
            realized_pnl=float(o.realized_pnl) if o.realized_pnl is not None else None,
            settled=bool(o.settled),
            created_at=o.created_at,
            category=categories.get(o.slug, "Other"),
            title=titles.get(o.slug, o.slug),
        )
        for o in orders
    ]
    report = compute_attribution(attributed_trades(legs, resolutions), top_n=top_n)
    return PortfolioAttributionResponse(
        win_rate=report.win_rate,
        roi=report.roi,
        total_realized_pnl=report.total_realized_pnl,
        total_cost=report.total_cost,
        n_trades=report.n_trades,
        top_trades=[_trade_to_response(t) for t in report.top_trades],
        bottom_trades=[_trade_to_response(t) for t in report.bottom_trades],
        monthly_pnl=report.monthly_pnl,
        category_pnl=report.category_pnl,
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )


@router.get("/portfolio/equity-curve", response_model=EquityCurveResponse)
async def get_portfolio_equity_curve(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EquityCurveResponse:
    """B5 — ordered daily equity snapshots for the authenticated user."""
    try:
        rows = (
            await db.scalars(
                select(PortfolioEquitySnapshot)
                .where(PortfolioEquitySnapshot.user_id == current_user.id)
                .order_by(PortfolioEquitySnapshot.snapshot_date.asc())
            )
        ).all()
    except (OperationalError, ProgrammingError) as exc:
        raise _portfolio_unavailable() from exc

    return EquityCurveResponse(
        points=[
            EquityCurvePoint(
                date=r.snapshot_date.isoformat(),
                cash_balance=float(r.cash_balance),
                positions_mtm=float(r.positions_mtm),
                equity=float(r.equity),
            )
            for r in rows
        ],
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )


@router.get("/portfolio/exposure", response_model=ExposureResponse)
async def get_portfolio_exposure(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposureResponse:
    """Aggregate open paper positions by correlated underlier (U04).

    Returns exposure groups sorted by total notional descending, plus a
    concentration flag when any single underlier exceeds 40 % of total open
    notional.  Deterministic math only — no LLM call.  Read-only endpoint.
    """
    try:
        all_positions = await _load_paper_orders(db, current_user.id.hex)
    except (OperationalError, ProgrammingError) as exc:
        raise _portfolio_unavailable() from exc

    open_positions = [p for p in all_positions if not p.settled]

    # Fetch DB category for each open market slug
    open_slugs = list({p.market_slug for p in open_positions})
    slug_to_category: dict[str, str] = {}
    if open_slugs:
        rows = (
            await db.execute(
                select(Market.slug, Market.category).where(Market.slug.in_(open_slugs))
            )
        ).all()
        slug_to_category = {str(slug): str(cat or "") for slug, cat in rows}

    inputs = [
        PositionInput(
            market_slug=p.market_slug,
            outcome=p.outcome,
            shares=p.shares,
            avg_cost=p.avg_cost,
            category=slug_to_category.get(p.market_slug),
        )
        for p in open_positions
        if p.shares > 0 and p.avg_cost > 0
    ]

    summary = compute_exposure(inputs)

    return ExposureResponse(
        total_open_notional=summary.total_open_notional,
        groups=[
            ExposureGroupResponse(
                underlier=g.underlier,
                position_count=g.position_count,
                net_directional=g.net_directional,
                total_notional=g.total_notional,
                pct_of_total=g.pct_of_total,
                concentrated=g.concentrated,
                positions=g.positions,
            )
            for g in summary.groups
        ],
        has_concentration=summary.has_concentration,
        concentrated_underliers=summary.concentrated_underliers,
        paper_trading_only=True,
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
    except (OperationalError, ProgrammingError) as exc:
        raise _portfolio_unavailable() from exc

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
