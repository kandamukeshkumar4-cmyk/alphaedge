"""Explicit paper costs for pod ledger rows; no zero-cost fill fiction."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.signals.arbitrage import SignalCosts, kalshi_taker_fee

_MONEY = Decimal("0.0001")


def estimate_entry_fee(*, source: str, price: Decimal, quantity: Decimal, config: dict) -> Decimal:
    """Calculate known venue costs, or use an explicit configured estimate.

    A configured value is intentionally required for sources without a known
    schedule. The runner rejects a proposed entry where the source has neither
    a supported schedule nor an explicit estimate.
    """
    normalized = source.strip().lower()
    if normalized == "kalshi":
        rate = Decimal(str(config.get("kalshi_taker_fee_rate", SignalCosts().kalshi_taker_fee_rate)))
        return (kalshi_taker_fee(price, rate) * quantity).quantize(_MONEY, rounding=ROUND_HALF_UP)
    configured = config.get("fee_per_contract")
    if configured is None:
        raise ValueError(f"no honest fee estimate configured for source={normalized or 'unknown'}")
    return (Decimal(str(configured)) * quantity).quantize(_MONEY, rounding=ROUND_HALF_UP)
