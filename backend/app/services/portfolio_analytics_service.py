"""Loop V92 — per-user paper portfolio analytics (read-only).

Computes pnl_series + summary (+ calibration buckets) over the caller's own
``paper_orders``. Reuses existing attribution (settlement-safe P&L) and the
portfolio mark-to-market helpers — never invents settlement math, never
touches the order path.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, MarketResolution, PaperOrder, User
from app.services.analytics_attribution import (
    OrderLeg,
    attributed_trades,
)


def _empty_payload() -> dict[str, Any]:
    return {
        "pnl_series": [],
        "summary": {
            "total_realized": 0.0,
            "total_unrealized": 0.0,
            "win_rate": 0.0,
            "trades_closed": 0,
            "trades_open": 0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_hold_hours": 0.0,
        },
        "calibration": {
            "buckets": [],
            "paper_trading_only": True,
        },
    }


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def _avg_hold_hours(
    orders: list[PaperOrder],
    resolutions: dict[str, str],
    resolved_at: dict[str, datetime | None],
) -> float:
    """Mean hours BUY -> matching SELL, or BUY -> market resolve when settled."""
    buy_times: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    holds: list[float] = []

    for order in sorted(orders, key=lambda o: (_as_utc(o.created_at), str(o.id))):
        key = (order.slug, str(order.outcome).upper())
        action = str(order.action).upper()
        created = _as_utc(order.created_at)
        if action == "BUY":
            buy_times[key].append(created)
            continue
        if action == "SELL" and buy_times[key]:
            buy_dt = buy_times[key].pop(0)
            delta_h = (created - buy_dt).total_seconds() / 3600.0
            if delta_h >= 0:
                holds.append(delta_h)

    for key, times in buy_times.items():
        slug, _outcome = key
        if slug not in resolutions:
            continue
        end = resolved_at.get(slug)
        if end is None:
            continue
        end_utc = _as_utc(end)
        for buy_dt in times:
            delta_h = (end_utc - buy_dt).total_seconds() / 3600.0
            if delta_h >= 0:
                holds.append(delta_h)

    if not holds:
        return 0.0
    return round(sum(holds) / len(holds), 4)


def _build_pnl_series(
    *,
    days: int,
    today: date,
    closed_events: list[tuple[date, float]],
    total_realized: float,
    total_unrealized: float,
    portfolio_value: float,
    has_activity: bool,
) -> list[dict[str, float | str]]:
    if not has_activity or days < 1:
        return []

    realized_by_day: dict[date, float] = defaultdict(float)
    for event_day, pnl in closed_events:
        realized_by_day[event_day] += pnl

    start = today - timedelta(days=days - 1)
    initial = round(portfolio_value - total_realized - total_unrealized, 4)

    series: list[dict[str, float | str]] = []
    cumulative = 0.0
    cursor = start
    while cursor <= today:
        cumulative = round(cumulative + realized_by_day.get(cursor, 0.0), 4)
        unrealized = total_unrealized if cursor == today else 0.0
        equity = round(initial + cumulative + unrealized, 4)
        series.append(
            {
                "date": cursor.isoformat(),
                "realized_pnl": cumulative,
                "unrealized_pnl": round(unrealized, 4),
                "equity": equity,
            }
        )
        cursor += timedelta(days=1)
    return series

async def compute_portfolio_analytics(
    db: AsyncSession,
    user: User,
    days: int,
) -> dict[str, Any]:
    """Return the frozen portfolio analytics contract for one paper user.

    Empty book -> zeros + empty arrays (never raises on missing data).
    """
    empty = _empty_payload()
    if days < 1:
        return empty

    try:
        orders = list(
            (
                await db.scalars(
                    select(PaperOrder)
                    .where(PaperOrder.user_id == user.id)
                    .order_by(PaperOrder.created_at.asc(), PaperOrder.id.asc())
                )
            ).all()
        )
    except Exception:
        return empty

    if not orders:
        return empty

    from app.api.v1.portfolio import (
        _enrich_live_pnl,
        _latest_implied_yes_by_slug,
        _load_paper_orders,
    )

    try:
        positions = await _load_paper_orders(db, user.id.hex)
    except Exception:
        return empty

    open_positions = [p for p in positions if not p.settled]
    paper_balance = float(user.paper_balance)
    slugs_open = list({p.market_slug for p in open_positions})
    try:
        implied = await _latest_implied_yes_by_slug(db, slugs_open)
        total_unrealized, portfolio_value = _enrich_live_pnl(
            list(open_positions), implied, paper_balance
        )
    except Exception:
        total_unrealized, portfolio_value = 0.0, paper_balance

    all_slugs = list({o.slug for o in orders})
    resolutions: dict[str, str] = {}
    resolved_at: dict[str, datetime | None] = {}
    titles: dict[str, str] = {}
    categories: dict[str, str] = {}
    if all_slugs:
        res_rows = (
            await db.execute(
                select(MarketResolution.slug, MarketResolution.outcome).where(
                    MarketResolution.slug.in_(all_slugs)
                )
            )
        ).all()
        resolutions = {str(s): str(o) for s, o in res_rows}
        market_rows = (
            await db.execute(
                select(
                    Market.slug,
                    Market.resolved_at,
                    Market.title,
                    Market.category,
                ).where(Market.slug.in_(all_slugs))
            )
        ).all()
        for slug, res_at, title, cat in market_rows:
            resolved_at[str(slug)] = res_at
            titles[str(slug)] = str(title or slug)
            categories[str(slug)] = str(cat or "Other")

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
            created_at=_as_utc(o.created_at),
            category=categories.get(o.slug, "Other"),
            title=titles.get(o.slug, o.slug),
        )
        for o in orders
    ]
    closed = attributed_trades(legs, resolutions)
    pnls = [t.realized_pnl for t in closed]
    total_realized = round(sum(pnls), 4) if pnls else 0.0
    trades_closed = len(closed)
    wins = sum(1 for p in pnls if p > 0)
    win_rate = round(wins / trades_closed, 4) if trades_closed else 0.0
    best_trade = round(max(pnls), 4) if pnls else 0.0
    worst_trade = round(min(pnls), 4) if pnls else 0.0
    avg_hold = _avg_hold_hours(orders, resolutions, resolved_at)

    today = datetime.now(UTC).date()
    closed_events = [
        (_as_utc(t.created_at).date(), float(t.realized_pnl)) for t in closed
    ]
    series = _build_pnl_series(
        days=days,
        today=today,
        closed_events=closed_events,
        total_realized=total_realized,
        total_unrealized=float(total_unrealized),
        portfolio_value=float(portfolio_value),
        has_activity=True,
    )

    return {
        "pnl_series": series,
        "summary": {
            "total_realized": float(total_realized),
            "total_unrealized": round(float(total_unrealized), 4),
            "win_rate": float(win_rate),
            "trades_closed": int(trades_closed),
            "trades_open": len(open_positions),
            "best_trade": float(best_trade),
            "worst_trade": float(worst_trade),
            "avg_hold_hours": float(avg_hold),
        },
        "calibration": {
            "buckets": [],
            "paper_trading_only": True,
        },
    }

