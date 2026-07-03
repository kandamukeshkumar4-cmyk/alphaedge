"""Portfolio risk metrics (E12) — pure math over paper trades. Clean-room.

All functions are DB-free and deterministic so they unit-test exactly.
Metrics are computed over SETTLED (realized) trades for the return series and
over OPEN positions for exposure. Paper trading only — these describe the
simulated book, never advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class ClosedTrade:
    """One realized (settled/sold) position: what it cost and what it returned."""

    cost: float
    realized_pnl: float


@dataclass(frozen=True)
class OpenExposure:
    category: str
    cost: float


@dataclass(frozen=True)
class RiskMetrics:
    n_closed: int
    total_realized_pnl: float
    win_rate: float | None  # None when no closed trades
    max_drawdown: float  # most negative dip of the cumulative realized-PnL curve
    sharpe: float | None  # per-trade Sharpe (mean/std of per-trade returns); None if <2 trades
    exposure_by_category: dict[str, float]  # open cost per category
    exposure_pct_by_category: dict[str, float]  # share of total open cost, 0..100


def max_drawdown(pnl_series: list[float]) -> float:
    """Largest peak-to-trough fall of the cumulative PnL curve (>= 0.0).

    Input is the ordered list of per-trade realized PnLs.
    """
    peak = 0.0
    cumulative = 0.0
    worst = 0.0
    for pnl in pnl_series:
        cumulative += pnl
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return round(worst, 4)


def per_trade_sharpe(trades: list[ClosedTrade]) -> float | None:
    """Mean / stdev of per-trade returns (pnl over cost). None with <2 usable trades.

    NOT annualized — event markets have no natural period; this is a
    consistency score for the trade series, labeled as such in the UI.
    """
    returns = [t.realized_pnl / t.cost for t in trades if t.cost > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = sqrt(variance)
    if std < 1e-9:  # flat series (allowing float noise) has no meaningful score
        return None
    return round(mean / std, 4)


def compute_risk_metrics(
    closed: list[ClosedTrade],
    open_exposures: list[OpenExposure],
) -> RiskMetrics:
    wins = sum(1 for t in closed if t.realized_pnl > 0)
    total_open = sum(e.cost for e in open_exposures)

    by_cat: dict[str, float] = {}
    for e in open_exposures:
        by_cat[e.category] = round(by_cat.get(e.category, 0.0) + e.cost, 2)
    pct_by_cat = {
        cat: round(cost / total_open * 100.0, 2) if total_open > 0 else 0.0
        for cat, cost in by_cat.items()
    }

    return RiskMetrics(
        n_closed=len(closed),
        total_realized_pnl=round(sum(t.realized_pnl for t in closed), 4),
        win_rate=round(wins / len(closed), 4) if closed else None,
        max_drawdown=max_drawdown([t.realized_pnl for t in closed]),
        sharpe=per_trade_sharpe(closed),
        exposure_by_category=by_cat,
        exposure_pct_by_category=pct_by_cat,
    )
