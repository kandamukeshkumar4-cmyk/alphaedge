"""Performance attribution over settled paper trades (Loop V15 B2).

Avoids the E12 `_load_paper_orders` double-count: that query adds
``SUM(realized_pnl)`` (from SELL closes) **and** a settlement CASE on remaining
shares. Attribution instead treats legs disjointly:

* SELL rows contribute ``realized_pnl`` only (close-before-resolve).
* Remaining net BUY shares at resolve contribute settlement PnL once
  (win = shares − cost_basis, loss = −cost_basis).
* BUY rows never also add a stored ``realized_pnl`` on top of settlement.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class OrderLeg:
    """One paper_orders row needed for attribution."""

    id: str
    slug: str
    outcome: str
    action: str  # BUY | SELL
    shares: float
    cost: float
    realized_pnl: float | None
    settled: bool
    created_at: datetime
    category: str = "Other"
    title: str = ""


@dataclass(frozen=True)
class AttributedTrade:
    order_id: str
    slug: str
    title: str
    category: str
    side: str  # BUY | SELL | SETTLE
    cost: float
    realized_pnl: float
    created_at: datetime


@dataclass(frozen=True)
class AttributionReport:
    win_rate: float | None
    roi: float
    total_realized_pnl: float
    total_cost: float
    n_trades: int
    top_trades: list[AttributedTrade]
    bottom_trades: list[AttributedTrade]
    monthly_pnl: dict[str, float]  # YYYY-MM -> pnl
    category_pnl: dict[str, float]


def _settlement_pnl(shares: float, cost: float, outcome: str, resolution: str | None) -> float:
    if resolution is None:
        return 0.0
    if outcome.upper() == resolution.upper():
        return round(shares - cost, 4)
    return round(0.0 - cost, 4)


def attributed_trades(
    orders: Iterable[OrderLeg],
    resolutions: dict[str, str],
) -> list[AttributedTrade]:
    """Build disjoint attributed legs (no E12 double-count)."""
    settled = [o for o in orders if o.settled]
    out: list[AttributedTrade] = []

    # SELL closes — use stored realized_pnl only.
    for o in settled:
        if o.action.upper() != "SELL":
            continue
        if o.realized_pnl is None:
            continue
        out.append(
            AttributedTrade(
                order_id=o.id,
                slug=o.slug,
                title=o.title or o.slug,
                category=o.category or "Other",
                side="SELL",
                cost=round(float(o.cost), 4),
                realized_pnl=round(float(o.realized_pnl), 4),
                created_at=o.created_at,
            )
        )

    # Remaining net BUY shares per (slug, outcome) get settlement once.
    groups: dict[tuple[str, str], list[OrderLeg]] = defaultdict(list)
    for o in settled:
        groups[(o.slug, o.outcome.upper())].append(o)

    for (slug, outcome), legs in groups.items():
        net_shares = 0.0
        buy_shares = 0.0
        buy_cost = 0.0
        category = "Other"
        title = slug
        latest = legs[0].created_at
        buy_ids: list[str] = []
        for o in legs:
            category = o.category or category
            title = o.title or title
            if o.created_at > latest:
                latest = o.created_at
            if o.action.upper() == "SELL":
                net_shares -= o.shares
            else:
                net_shares += o.shares
                buy_shares += o.shares
                buy_cost += o.cost
                buy_ids.append(o.id)
        if net_shares <= 1e-9 or buy_shares <= 1e-9:
            continue
        cost_basis = buy_cost * (net_shares / buy_shares)
        pnl = _settlement_pnl(net_shares, cost_basis, outcome, resolutions.get(slug))
        out.append(
            AttributedTrade(
                order_id=buy_ids[-1] if buy_ids else f"{slug}:{outcome}:settle",
                slug=slug,
                title=title,
                category=category,
                side="SETTLE",
                cost=round(cost_basis, 4),
                realized_pnl=pnl,
                created_at=latest,
            )
        )

    out.sort(key=lambda t: t.created_at)
    return out


def compute_attribution(
    trades: list[AttributedTrade],
    *,
    top_n: int = 5,
) -> AttributionReport:
    if not trades:
        return AttributionReport(
            win_rate=None,
            roi=0.0,
            total_realized_pnl=0.0,
            total_cost=0.0,
            n_trades=0,
            top_trades=[],
            bottom_trades=[],
            monthly_pnl={},
            category_pnl={},
        )

    total_pnl = round(sum(t.realized_pnl for t in trades), 4)
    total_cost = round(sum(t.cost for t in trades if t.cost > 0), 4)
    wins = sum(1 for t in trades if t.realized_pnl > 0)
    win_rate = round(wins / len(trades), 4)
    roi = round(total_pnl / total_cost, 4) if total_cost > 0 else 0.0

    by_pnl = sorted(trades, key=lambda t: t.realized_pnl, reverse=True)
    n = max(1, top_n)
    top = by_pnl[:n]
    bottom = list(reversed(by_pnl[-n:])) if len(by_pnl) >= n else list(reversed(by_pnl))

    monthly: dict[str, float] = defaultdict(float)
    by_cat: dict[str, float] = defaultdict(float)
    for t in trades:
        month = t.created_at.strftime("%Y-%m")
        monthly[month] = round(monthly[month] + t.realized_pnl, 4)
        cat = t.category or "Other"
        by_cat[cat] = round(by_cat[cat] + t.realized_pnl, 4)

    return AttributionReport(
        win_rate=win_rate,
        roi=roi,
        total_realized_pnl=total_pnl,
        total_cost=total_cost,
        n_trades=len(trades),
        top_trades=top,
        bottom_trades=bottom,
        monthly_pnl=dict(sorted(monthly.items())),
        category_pnl=dict(sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)),
    )
