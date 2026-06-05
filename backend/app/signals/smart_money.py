from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
