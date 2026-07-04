"""U10 — Realistic fill model for backtest replay.

Fills are NEVER at perfect mid-price — the market charges a spread and there is
slippage proportional to the order size. This module is pure (no DB, no I/O).

Slippage function (documented, unit-tested):
    fill_price(side, mid, spread, size) = mid ± half_spread + size_slippage
    where
        half_spread = spread / 2
        size_slippage = slippage_per_unit * size   (clamped ≥ 0)
        YES buy  → mid + half_spread + size_slippage   (worse, you pay more)
        NO  buy  → (1 - mid) + half_spread + size_slippage  (worse)
        YES sell → mid - half_spread - size_slippage  (worse, you receive less)

Boundary guarantees:
    - At zero spread and zero size: fill_price == mid  (clean mid fill)
    - fill_price is always in [0.001, 0.999] (clipped)

No order-path imports — this module must never import OrderBookService or RiskService.
PAPER_TRADING_ONLY: this is a pure simulation; no real funds or exchange calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TradeSide = Literal["yes_buy", "yes_sell", "no_buy"]


@dataclass(frozen=True)
class FillResult:
    """Result of a single simulated fill."""

    side: TradeSide
    mid_price: float
    spread: float
    size: float
    fill_price: float
    slippage: float  # fill_price - mid_price (negative = worse for seller)
    slippage_abs: float  # abs(slippage)


# Default spread and slippage values (intentionally conservative).
DEFAULT_SPREAD: float = 0.02   # 2-cent spread is common on binary markets
DEFAULT_SLIPPAGE_PER_UNIT: float = 0.001  # 0.1 cent per share ordered


def compute_fill(
    side: TradeSide,
    mid_price: float,
    *,
    spread: float = DEFAULT_SPREAD,
    size: float = 1.0,
    slippage_per_unit: float = DEFAULT_SLIPPAGE_PER_UNIT,
) -> FillResult:
    """Compute the realistic fill price for a paper trade.

    Parameters
    ----------
    side:
        "yes_buy"  — buying YES shares (long position)
        "yes_sell" — selling YES shares (closing a long)
        "no_buy"   — buying NO shares (short position on YES)
    mid_price:
        The mid-market implied YES probability, in [0, 1].
    spread:
        Full bid-ask spread in probability units.  Must be >= 0.
    size:
        Number of shares / contracts.  Must be >= 0.
    slippage_per_unit:
        Additional slippage per share ordered.  Must be >= 0.

    Returns
    -------
    FillResult with fill_price clipped to [0.001, 0.999].
    """
    if not (0.0 <= mid_price <= 1.0):
        raise ValueError(f"mid_price must be in [0, 1]; got {mid_price}")
    if spread < 0:
        raise ValueError(f"spread must be >= 0; got {spread}")
    if size < 0:
        raise ValueError(f"size must be >= 0; got {size}")
    if slippage_per_unit < 0:
        raise ValueError(f"slippage_per_unit must be >= 0; got {slippage_per_unit}")

    half_spread = spread / 2.0
    size_slip = slippage_per_unit * size

    if side == "yes_buy":
        # Paying the ask: mid + half_spread + size_slippage
        fill = mid_price + half_spread + size_slip
        slippage = fill - mid_price
    elif side == "yes_sell":
        # Hitting the bid: mid - half_spread - size_slippage
        fill = mid_price - half_spread - size_slip
        slippage = fill - mid_price  # negative: you receive less than mid
    elif side == "no_buy":
        # Buying NO = selling YES on the other side.
        # NO mid = 1 - mid_price; buyer pays the ask on NO side.
        no_mid = 1.0 - mid_price
        fill = no_mid + half_spread + size_slip
        slippage = fill - no_mid  # measured vs NO mid
    else:
        raise ValueError(f"Unknown side: {side!r}")

    fill = max(0.001, min(0.999, fill))
    return FillResult(
        side=side,
        mid_price=mid_price,
        spread=spread,
        size=size,
        fill_price=fill,
        slippage=slippage,
        slippage_abs=abs(slippage),
    )
