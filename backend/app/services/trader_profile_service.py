"""U13 — Trader profile service.

Deterministic, read-only math derived EXCLUSIVELY from the user's own
paper-trade history (paper_orders table).  No external data sources,
no LLM-generated numbers, no fabricated stats.

Privacy hard requirement (§G):
- Profile uses ONLY in-app paper activity.
- A new user with fewer than MIN_TRADES_FOR_PROFILE trades sees an honest
  empty state — no fabricated statistics.
- No external account, identity provider, or third-party data is consulted.

Order-path guardrail: this module MUST NOT import OrderBookService or RiskService.

Attribution (ideas, no code copied):
- CloddsBot (MIT) — self-hosted activity-observing agent pattern.
- artvandelay/polymarket-agents (MIT) — tool framework + memory layering.
- TradingAgents (Apache-2.0) — performance-feedback loop design.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.services.exposure_service import derive_underlier_key

# Minimum trade count before any stats are reported.
# Below this threshold the profile is empty-state (no fabricated numbers).
MIN_TRADES_FOR_PROFILE: int = 5


# ── Input types ──────────────────────────────────────────────────────────────


@dataclass
class TradeRecord:
    """Minimal view of one paper_order row needed for profiling.

    Callers construct these from the ORM; the service never touches the DB.
    """

    slug: str
    side: str          # "YES" or "NO"
    shares: Decimal
    price: Decimal
    cost: Decimal
    action: str        # "BUY" or "SELL"
    realized_pnl: Optional[Decimal]
    settled: bool
    created_at: datetime
    category: Optional[str] = None   # optional market category from catalog


# ── Output types ─────────────────────────────────────────────────────────────


@dataclass
class CategoryStats:
    category: str
    trade_count: int
    win_count: int          # settled BUY orders with realized_pnl > 0
    loss_count: int
    win_rate: float         # 0.0–1.0; –1.0 if no settled trades yet


@dataclass
class TraderProfile:
    """Derived trading-behaviour profile.

    All numbers are deterministic math over the user's paper history.
    When has_data is False, every field is set to its sentinel value and
    callers must show the honest empty state.
    """

    has_data: bool                  # True iff >= MIN_TRADES_FOR_PROFILE trades

    # Present only when has_data is True —————————————
    # Category preferences (sorted by trade_count desc)
    favorite_categories: list[str] = field(default_factory=list)
    category_stats: list[CategoryStats] = field(default_factory=list)

    # Sizing behaviour
    avg_cost_usd: float = 0.0       # mean cost (shares × price) per BUY
    bankroll_usd: float = 0.0       # paper_balance at compute time
    avg_size_pct_bankroll: float = 0.0  # avg_cost / bankroll × 100

    # Holding period
    avg_hold_hours: float = 0.0     # mean hours between BUY and matching SELL/settlement

    # Entry style (optional — only set when timing data allows)
    entry_style: Optional[str] = None   # "momentum" | "fade" | None

    # Streak / tilt detection
    current_streak: int = 0         # +N = N consecutive wins, -N = N consecutive losses
    sizes_up_after_losses: bool = False  # True if avg cost increases after a losing streak
    tilt_multiplier: float = 1.0    # avg_cost(after_loss) / avg_cost(normal)

    # Overall win rate across all settled trades
    overall_win_rate: float = -1.0  # –1.0 = no settled trades yet

    # Data provenance note (always shown — part of the privacy contract)
    source_note: str = "Derived only from your paper activity in this app."


# ── Derivation logic ─────────────────────────────────────────────────────────


def _infer_category(trade: TradeRecord) -> str:
    """Map a trade to a category string for grouping."""
    if trade.category:
        return trade.category.upper()
    underlier = derive_underlier_key(trade.slug)
    prefix = underlier.split(":")[0]
    # Map underlier prefixes to readable categories
    _PREFIX_MAP: dict[str, str] = {
        "NBA": "NBA",
        "FIFA_WC2026": "FIFA_WC2026",
        "CRYPTO": "CRYPTO",
        "ELECTION": "ELECTION",
    }
    return _PREFIX_MAP.get(prefix, "OTHER")


def _compute_category_stats(buys: list[TradeRecord]) -> list[CategoryStats]:
    """Compute per-category trade counts and win rates from BUY records."""
    from collections import defaultdict

    counts: dict[str, int] = defaultdict(int)
    wins: dict[str, int] = defaultdict(int)
    losses: dict[str, int] = defaultdict(int)

    for t in buys:
        cat = _infer_category(t)
        counts[cat] += 1
        if t.settled and t.realized_pnl is not None:
            if t.realized_pnl > 0:
                wins[cat] += 1
            else:
                losses[cat] += 1

    stats: list[CategoryStats] = []
    for cat, cnt in sorted(counts.items(), key=lambda kv: -kv[1]):
        settled = wins[cat] + losses[cat]
        win_rate = wins[cat] / settled if settled > 0 else -1.0
        stats.append(
            CategoryStats(
                category=cat,
                trade_count=cnt,
                win_count=wins[cat],
                loss_count=losses[cat],
                win_rate=win_rate,
            )
        )
    return stats


def _compute_avg_hold_hours(trades: list[TradeRecord]) -> float:
    """Estimate average hold period in hours.

    Strategy: pair each SELL (or settled BUY) with the most-recent preceding
    BUY on the same slug.  Uses wall-clock time from created_at.
    """
    # Group BUYs by slug in chronological order
    from collections import defaultdict

    buy_times: dict[str, list[datetime]] = defaultdict(list)
    hold_hours: list[float] = []

    for t in sorted(trades, key=lambda r: r.created_at):
        if t.action == "BUY":
            buy_times[t.slug].append(t.created_at)
        elif t.action == "SELL" and buy_times[t.slug]:
            buy_dt = buy_times[t.slug].pop(0)
            sell_dt = t.created_at
            # Ensure both datetimes are timezone-aware for safe subtraction
            if buy_dt.tzinfo is None:
                buy_dt = buy_dt.replace(tzinfo=timezone.utc)
            if sell_dt.tzinfo is None:
                sell_dt = sell_dt.replace(tzinfo=timezone.utc)
            delta_h = (sell_dt - buy_dt).total_seconds() / 3600.0
            if delta_h >= 0:
                hold_hours.append(delta_h)

    return sum(hold_hours) / len(hold_hours) if hold_hours else 0.0


def _detect_tilt(buys: list[TradeRecord]) -> tuple[int, bool, float]:
    """Detect streak and tilt (sizing up after losses).

    Returns (current_streak, sizes_up_after_losses, tilt_multiplier).

    Only settled BUY trades are used for streak calculation.
    current_streak: +N = N consecutive wins, -N = N consecutive losses.
    """
    settled_buys = [t for t in buys if t.settled and t.realized_pnl is not None]
    settled_buys.sort(key=lambda t: t.created_at)

    if not settled_buys:
        return 0, False, 1.0

    # Streak from most-recent onwards
    streak = 0
    for t in reversed(settled_buys):
        if streak == 0:
            streak = 1 if t.realized_pnl > 0 else -1  # type: ignore[operator]
        elif streak > 0 and t.realized_pnl > 0:  # type: ignore[operator]
            streak += 1
        elif streak < 0 and t.realized_pnl <= 0:  # type: ignore[operator]
            streak -= 1
        else:
            break

    # Tilt detection: compare avg cost in trades after a losing streak (≥2 losses)
    # vs avg cost in trades after winning / neutral periods.
    # Requires at least 4 settled trades to make this meaningful.
    if len(settled_buys) < 4:
        return streak, False, 1.0

    after_loss_costs: list[Decimal] = []
    normal_costs: list[Decimal] = []
    in_loss_streak = False
    consecutive_losses = 0

    for i, t in enumerate(settled_buys):
        if i == 0:
            if t.realized_pnl <= 0:  # type: ignore[operator]
                consecutive_losses = 1
            continue
        # Classify trade i based on the run ending at i-1
        if in_loss_streak:
            after_loss_costs.append(t.cost)
        else:
            normal_costs.append(t.cost)

        # Update streak state
        if t.realized_pnl <= 0:  # type: ignore[operator]
            consecutive_losses += 1
            in_loss_streak = consecutive_losses >= 2
        else:
            consecutive_losses = 0
            in_loss_streak = False

    if not after_loss_costs or not normal_costs:
        return streak, False, 1.0

    avg_after = float(sum(after_loss_costs)) / len(after_loss_costs)
    avg_normal = float(sum(normal_costs)) / len(normal_costs)

    if avg_normal == 0:
        return streak, False, 1.0

    tilt_mult = avg_after / avg_normal
    sizes_up = tilt_mult >= 1.2  # ≥20 % larger average cost after losses

    return streak, sizes_up, round(tilt_mult, 2)


def compute_trader_profile(
    trades: list[TradeRecord],
    bankroll_usd: float = 0.0,
) -> TraderProfile:
    """Derive a TraderProfile from a list of TradeRecord objects.

    This is the ONLY public derivation function.  It is deterministic:
    given the same input list it always returns the same output.

    Privacy contract: callers must pass ONLY records from the in-app
    paper_orders table for the authenticated user.  No external data.

    Args:
        trades:       All paper_orders for the user (any action/settled state).
        bankroll_usd: Current paper_balance for the user.

    Returns:
        TraderProfile.  has_data=False when len(trades) < MIN_TRADES_FOR_PROFILE.
    """
    if len(trades) < MIN_TRADES_FOR_PROFILE:
        return TraderProfile(has_data=False)

    buys = [t for t in trades if t.action == "BUY"]
    if not buys:
        return TraderProfile(has_data=False)

    # Category stats
    cat_stats = _compute_category_stats(buys)
    favorite_categories = [s.category for s in cat_stats[:3]]

    # Sizing
    costs = [float(t.cost) for t in buys]
    avg_cost = sum(costs) / len(costs) if costs else 0.0
    avg_size_pct = (avg_cost / bankroll_usd * 100.0) if bankroll_usd > 0 else 0.0

    # Hold period
    avg_hold = _compute_avg_hold_hours(trades)

    # Overall win rate
    settled = [t for t in buys if t.settled and t.realized_pnl is not None]
    if settled:
        wins = sum(1 for t in settled if t.realized_pnl > 0)  # type: ignore[operator]
        overall_wr = wins / len(settled)
    else:
        overall_wr = -1.0

    # Tilt / streak
    streak, sizes_up, tilt_mult = _detect_tilt(buys)

    return TraderProfile(
        has_data=True,
        favorite_categories=favorite_categories,
        category_stats=cat_stats,
        avg_cost_usd=round(avg_cost, 2),
        bankroll_usd=round(bankroll_usd, 2),
        avg_size_pct_bankroll=round(avg_size_pct, 2),
        avg_hold_hours=round(avg_hold, 2),
        entry_style=None,  # timing-based entry style requires price-move data; omit honestly
        current_streak=streak,
        sizes_up_after_losses=sizes_up,
        tilt_multiplier=tilt_mult,
        overall_win_rate=round(overall_wr, 4) if overall_wr >= 0 else -1.0,
        source_note="Derived only from your paper activity in this app.",
    )


# ── Deviation detection ───────────────────────────────────────────────────────


def detect_size_deviation(
    proposed_cost: float,
    profile: TraderProfile,
    multiplier_threshold: float = 2.0,
) -> Optional[str]:
    """Return a human-readable deviation note if the proposed bet deviates
    from the user's pattern, else None.

    Returns None when:
    - profile.has_data is False (new user — never fabricate a comparison)
    - avg_cost_usd is zero
    - proposed_cost / avg_cost < multiplier_threshold

    Example return: "This bet is 3.1x your usual position size."
    """
    if not profile.has_data:
        return None
    if profile.avg_cost_usd <= 0:
        return None
    ratio = proposed_cost / profile.avg_cost_usd
    if ratio < multiplier_threshold:
        return None
    return f"This bet is {ratio:.1f}x your usual position size."
