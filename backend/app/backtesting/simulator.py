"""Paper-trade simulator for backtest replay."""

from dataclasses import dataclass


@dataclass
class SimTrade:
    market_slug: str
    predicted_prob: float
    implied_yes: float
    outcome: int
    pnl: float


def simulate_trade(
    market_slug: str,
    predicted_prob: float,
    implied_yes: float,
    outcome: int,
    stake: float = 100.0,
    edge_threshold: float = 0.05,
) -> SimTrade | None:
    edge = predicted_prob - implied_yes
    if abs(edge) < edge_threshold:
        return None
    # Buy YES if model > market
    if edge > 0:
        cost = implied_yes * stake
        payout = stake * outcome
        pnl = payout - cost
    else:
        cost = (1 - implied_yes) * stake
        payout = stake * (1 - outcome)
        pnl = payout - cost
    return SimTrade(market_slug, predicted_prob, implied_yes, outcome, pnl)
