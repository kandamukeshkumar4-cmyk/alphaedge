from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP

from app.signals.matching import ResolutionMatch


MONEY = Decimal("0.0001")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class BinaryMarketQuote:
    platform: str
    market_id: str
    yes_price: Decimal
    no_price: Decimal


@dataclass(frozen=True)
class SignalCosts:
    kalshi_taker_fee_rate: Decimal = Decimal("0.0700")
    polymarket_gas_per_contract: Decimal = Decimal("0.0000")


@dataclass(frozen=True)
class ArbitrageLeg:
    market: BinaryMarketQuote
    outcome: str
    price: Decimal
    fee: Decimal


@dataclass(frozen=True)
class BinaryArbitrageSignal:
    yes_leg: ArbitrageLeg
    no_leg: ArbitrageLeg
    gross_cost: Decimal
    net_cost: Decimal
    gross_spread: Decimal
    net_spread: Decimal
    return_pct: float
    confidence: float
    resolution_status: str
    warning: str
    is_arbitrage: bool
    headline_eligible: bool


def find_binary_arbitrage(
    *,
    yes_market: BinaryMarketQuote,
    no_market: BinaryMarketQuote,
    resolution_match: ResolutionMatch,
    costs: SignalCosts | None = None,
) -> BinaryArbitrageSignal:
    signal_costs = costs or SignalCosts()
    yes_leg = ArbitrageLeg(
        market=yes_market,
        outcome="YES",
        price=yes_market.yes_price,
        fee=_platform_fee(yes_market.platform, yes_market.yes_price, signal_costs),
    )
    no_leg = ArbitrageLeg(
        market=no_market,
        outcome="NO",
        price=no_market.no_price,
        fee=_platform_fee(no_market.platform, no_market.no_price, signal_costs),
    )
    gross_cost = _money(yes_leg.price + no_leg.price)
    total_costs = yes_leg.fee + no_leg.fee
    net_cost = _money(gross_cost + total_costs)
    gross_spread = _money(Decimal("1.0000") - gross_cost)
    net_spread = _money(Decimal("1.0000") - net_cost)
    confirmed = resolution_match.confirmed
    is_arbitrage = confirmed and net_cost < Decimal("1.0000")
    return_pct = _ratio(net_spread, net_cost)
    warning = (
        "fee, slippage, liquidity, and resolution-term risk remain"
        if confirmed
        else resolution_match.warning or "resolution terms unconfirmed"
    )

    return BinaryArbitrageSignal(
        yes_leg=yes_leg,
        no_leg=no_leg,
        gross_cost=gross_cost,
        net_cost=net_cost,
        gross_spread=gross_spread,
        net_spread=net_spread,
        return_pct=return_pct,
        confidence=resolution_match.confidence,
        resolution_status=resolution_match.status,
        warning=warning,
        is_arbitrage=is_arbitrage,
        headline_eligible=is_arbitrage,
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def kalshi_taker_fee(price: Decimal, rate: Decimal = Decimal("0.0700")) -> Decimal:
    probability = _probability(price)
    raw_fee = rate * probability * (Decimal("1") - probability)
    return raw_fee.quantize(CENT, rounding=ROUND_UP)


def _platform_fee(platform: str, price: Decimal, costs: SignalCosts) -> Decimal:
    normalized = platform.strip().lower()
    if "kalshi" in normalized:
        return kalshi_taker_fee(price, costs.kalshi_taker_fee_rate)
    if "polymarket" in normalized:
        return _money(costs.polymarket_gas_per_contract)
    return Decimal("0.0000")


def _probability(value: Decimal) -> Decimal:
    probability = Decimal(str(value))
    if not Decimal("0") <= probability <= Decimal("1"):
        raise ValueError("signal prices must be between 0 and 1")
    return probability


def _ratio(numerator: Decimal, denominator: Decimal) -> float:
    if denominator <= 0:
        return 0.0
    return float((numerator / denominator).quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
