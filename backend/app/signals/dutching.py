from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


MONEY = Decimal("0.0001")


@dataclass(frozen=True)
class DutchingOutcome:
    name: str
    price: Decimal


@dataclass(frozen=True)
class DutchingLeg:
    outcome: str
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class DutchingResult:
    legs: tuple[DutchingLeg, ...]
    total_cost: Decimal
    guaranteed_payout: Decimal
    profit: Decimal
    return_pct: float
    coverage_status: str
    coverage_warning: str
    risk_free: bool


def evaluate_dutching(
    outcomes: list[DutchingOutcome],
    *,
    exhaustive: bool,
    mutually_exclusive: bool,
) -> DutchingResult:
    guaranteed_payout = Decimal("1.0000")
    legs = tuple(
        DutchingLeg(
            outcome=outcome.name,
            price=_money(outcome.price),
            quantity=guaranteed_payout,
        )
        for outcome in outcomes
    )
    total_cost = _money(sum((leg.price * leg.quantity for leg in legs), Decimal("0")))
    coverage_confirmed = exhaustive and mutually_exclusive
    risk_free = coverage_confirmed and total_cost < guaranteed_payout
    profit = _money(guaranteed_payout - total_cost) if risk_free else Decimal("0.0000")
    return_pct = _ratio(profit, total_cost)

    return DutchingResult(
        legs=legs,
        total_cost=total_cost,
        guaranteed_payout=guaranteed_payout,
        profit=profit,
        return_pct=return_pct,
        coverage_status="confirmed" if coverage_confirmed else "unconfirmed",
        coverage_warning="" if coverage_confirmed else "coverage not guaranteed",
        risk_free=risk_free,
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _ratio(numerator: Decimal, denominator: Decimal) -> float:
    if denominator <= 0:
        return 0.0
    return float((numerator / denominator).quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
