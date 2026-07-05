from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


@dataclass(frozen=True)
class WalletPerformance:
    roi: Decimal
    realized_pnl: Decimal
    total_trades: int


def is_qualified_wallet(
    performance: WalletPerformance,
    *,
    min_roi: Decimal = Decimal("0.1000"),
    min_realized_pnl: Decimal = Decimal("1.0000"),
    min_trades: int = 2,
) -> bool:
    return (
        performance.roi >= min_roi
        and performance.realized_pnl >= min_realized_pnl
        and performance.total_trades >= min_trades
    )


# --- T05: whale qualification (MrFadiAi rules, reimplemented) ---------------


@dataclass(frozen=True)
class WalletStats:
    """Derived from a wallet's resolved trade history."""

    resolved_count: int
    wins: int
    gross_profit: Decimal  # sum of winning PnL (>= 0)
    gross_loss: Decimal  # sum of |losing PnL| (>= 0)
    top_win: Decimal  # largest single winning PnL

    @property
    def accuracy(self) -> float:
        if self.resolved_count <= 0:
            return 0.0
        return self.wins / self.resolved_count

    @property
    def profit_factor(self) -> float:
        if self.gross_loss <= 0:
            # No losses: profit factor is "infinite" if there is profit, else 0.
            return float("inf") if self.gross_profit > 0 else 0.0
        return float(self.gross_profit / self.gross_loss)

    @property
    def total_pnl(self) -> Decimal:
        return self.gross_profit - self.gross_loss

    @property
    def top_win_share(self) -> float:
        if self.total_pnl <= 0:
            return 1.0  # can't diversify a non-positive book -> treat as concentrated
        return float(self.top_win / self.total_pnl)


@dataclass(frozen=True)
class QualificationResult:
    qualified: bool
    reasons: tuple[str, ...]


def qualify_whale(
    stats: WalletStats,
    *,
    min_resolved: int = 50,
    min_accuracy: float = 0.65,
    min_profit_factor: float = 1.5,
    max_top_win_share: float = 0.40,
) -> QualificationResult:
    """A wallet qualifies only if ALL rules pass. The one-hit-wonder guard excludes
    wallets whose top single win is >= max_top_win_share of total PnL (lucky, not
    skilled). Returns the reasons any rule failed for transparency."""
    reasons: list[str] = []
    if stats.resolved_count < min_resolved:
        reasons.append(f"resolved<{min_resolved}")
    if stats.accuracy < min_accuracy:
        reasons.append(f"accuracy<{min_accuracy}")
    if stats.profit_factor < min_profit_factor:
        reasons.append(f"profit_factor<{min_profit_factor}")
    if stats.top_win_share >= max_top_win_share:
        reasons.append("one_hit_wonder")
    return QualificationResult(qualified=not reasons, reasons=tuple(reasons))


# --- T05: position diffing -> whale_delta (Hermes layer 4) ------------------


class WhaleAction(str, Enum):
    ADD = "add"
    EXIT = "exit"
    FLIP = "flip"


@dataclass(frozen=True)
class WhalePositionState:
    market_slug: str
    outcome: str  # "YES" / "NO"
    size: Decimal


@dataclass(frozen=True)
class WhaleDelta:
    market_slug: str
    action: WhaleAction
    outcome: str
    direction: str  # "up" / "down"
    size_change: Decimal


def _direction_for(outcome: str, increasing: bool) -> str:
    """Increasing YES (or exiting NO) is bullish -> 'up'; the mirror is 'down'."""
    yes = outcome.upper() == "YES"
    if increasing:
        return "up" if yes else "down"
    return "down" if yes else "up"


def diff_whale_positions(
    prev: list[WhalePositionState],
    curr: list[WhalePositionState],
    *,
    min_size_change: Decimal = Decimal("0"),
) -> list[WhaleDelta]:
    """Detect adds / exits / flips between two position snapshots for one wallet.

    Keyed by market_slug (a wallet holds one side per market). A change of outcome
    on the same market is a FLIP; size up on the same outcome is ADD; size to zero
    (position gone) is EXIT.
    """
    prev_by_market = {p.market_slug: p for p in prev}
    curr_by_market = {c.market_slug: c for c in curr}
    deltas: list[WhaleDelta] = []

    for market_slug, c in curr_by_market.items():
        p = prev_by_market.get(market_slug)
        if p is None:
            # brand-new position == an add
            if c.size > min_size_change:
                deltas.append(
                    WhaleDelta(market_slug, WhaleAction.ADD, c.outcome,
                               _direction_for(c.outcome, True), c.size)
                )
            continue
        if p.outcome != c.outcome:
            # flipped sides: direction follows the NEW side being built
            deltas.append(
                WhaleDelta(market_slug, WhaleAction.FLIP, c.outcome,
                           _direction_for(c.outcome, True), c.size)
            )
            continue
        change = c.size - p.size
        if change > min_size_change:
            deltas.append(
                WhaleDelta(market_slug, WhaleAction.ADD, c.outcome,
                           _direction_for(c.outcome, True), change)
            )

    for market_slug, p in prev_by_market.items():
        if market_slug not in curr_by_market:
            # position fully exited
            deltas.append(
                WhaleDelta(market_slug, WhaleAction.EXIT, p.outcome,
                           _direction_for(p.outcome, False), p.size)
            )

    return deltas


def whale_delta_to_delta_event(delta: WhaleDelta, *, source: str = "polymarket.data-api"):
    """Convert a WhaleDelta into a diff-engine DeltaEvent (kind whale_delta)."""
    from datetime import UTC, datetime

    from app.signals.diff_engine import DeltaEvent, DeltaKind

    return DeltaEvent(
        market_slug=delta.market_slug,
        source=source,
        kind=DeltaKind.WHALE_DELTA,
        direction=delta.direction,
        magnitude=float(delta.size_change),
        detail={"action": delta.action.value, "outcome": delta.outcome},
        occurred_ts=datetime.now(UTC),
    )
