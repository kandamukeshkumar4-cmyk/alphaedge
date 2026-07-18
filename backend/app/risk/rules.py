"""Risk rules — all must pass before paper trade execution."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from app.core.config import get_settings


@dataclass
class OrderIntent:
    market_slug: str
    side: str
    outcome: str
    quantity: Decimal
    price: Optional[Decimal]
    predicted_prob: float
    confidence: float
    edge: float
    bankroll: Decimal
    current_drawdown: float
    minutes_before_start: int
    agent_enabled: bool = True
    expires_at: Optional[datetime] = None
    # Loop V23 A2: when True, RiskService rejects (admin-suspended JWT user).
    user_suspended: bool = False
    # Loop V59: exit/emergency SELL intents skip entry edge/confidence/timing
    # gates but still require PAPER_TRADING_ONLY + agent_enabled + not suspended.
    is_exit: bool = False
    # Required for exit intents: caller derives this from the owned position so
    # the risk layer can reject an oversized market SELL.
    exit_notional_cap: Optional[Decimal] = None


@dataclass(frozen=True)
class KellyStakeSuggestion:
    predicted_prob: float
    price: Decimal
    bankroll: Decimal
    edge: float
    kelly_fraction: float
    fractional_kelly_fraction: float
    cap_fraction: float
    stake_notional: Decimal
    quantity: Decimal
    capped: bool
    paper_trading_only: bool = True


class RiskService:
    MIN_EDGE = 0.05
    MIN_CONFIDENCE = 0.70
    MAX_DRAWDOWN = 0.15
    MAX_BET_PCT = 0.05
    FRACTIONAL_KELLY = 0.25

    def validate(self, intent: OrderIntent) -> tuple[bool, List[str]]:
        settings = get_settings()
        failures: List[str] = []

        if not settings.paper_trading_only:
            failures.append("PAPER_TRADING_ONLY must be true")
        if not intent.agent_enabled:
            failures.append("agent trading disabled")
        if intent.user_suspended:
            failures.append("user is suspended")
        bet_notional = (intent.price or Decimal("0.5")) * intent.quantity
        if intent.expires_at is not None:
            expires_at = intent.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                failures.append("order expiry must be in the future")
        if intent.is_exit:
            if intent.side.lower() != "sell":
                failures.append("exit intent must be sell")
            if intent.exit_notional_cap is None:
                failures.append("exit notional cap required")
            elif bet_notional > intent.exit_notional_cap:
                failures.append("exit exceeds position notional cap")
            return len(failures) == 0, failures
        if intent.edge < self.MIN_EDGE:
            failures.append(f"edge {intent.edge:.2%} < {self.MIN_EDGE:.0%}")
        if intent.confidence < self.MIN_CONFIDENCE:
            failures.append(f"confidence {intent.confidence:.2f} < {self.MIN_CONFIDENCE}")
        if intent.current_drawdown >= self.MAX_DRAWDOWN:
            failures.append(f"drawdown {intent.current_drawdown:.2%} >= {self.MAX_DRAWDOWN:.0%}")
        if bet_notional > intent.bankroll * Decimal(str(self.MAX_BET_PCT)):
            failures.append("bet exceeds max % bankroll")
        if intent.minutes_before_start < 5:
            failures.append("too close to game start")
        return len(failures) == 0, failures

    def suggest_stake(self, intent: OrderIntent) -> KellyStakeSuggestion:
        predicted_prob = intent.predicted_prob
        if intent.outcome.lower() == "no":
            predicted_prob = 1.0 - predicted_prob
        return suggest_fractional_kelly_stake(
            predicted_prob=predicted_prob,
            price=intent.price or Decimal("0.5"),
            bankroll=intent.bankroll,
            max_bet_pct=self.MAX_BET_PCT,
            fractional_kelly=self.FRACTIONAL_KELLY,
        )


def suggest_fractional_kelly_stake(
    predicted_prob: float,
    price: Decimal,
    bankroll: Decimal,
    max_bet_pct: float = RiskService.MAX_BET_PCT,
    fractional_kelly: float = RiskService.FRACTIONAL_KELLY,
) -> KellyStakeSuggestion:
    probability = _probability(predicted_prob)
    normalized_price = _price(price)
    normalized_bankroll = _money(bankroll)
    cap_fraction = max(0.0, float(max_bet_pct))
    edge = probability - float(normalized_price)
    kelly_fraction = _binary_yes_kelly_fraction(probability, float(normalized_price))
    fractional_kelly_fraction = max(0.0, kelly_fraction * max(0.0, float(fractional_kelly)))
    stake_fraction = min(fractional_kelly_fraction, cap_fraction)
    stake_notional = _money(normalized_bankroll * Decimal(str(stake_fraction)))
    quantity = _money(stake_notional / normalized_price) if normalized_price > 0 else Decimal("0.0000")
    return KellyStakeSuggestion(
        predicted_prob=probability,
        price=normalized_price,
        bankroll=normalized_bankroll,
        edge=round(edge, 10),
        kelly_fraction=kelly_fraction,
        fractional_kelly_fraction=fractional_kelly_fraction,
        cap_fraction=cap_fraction,
        stake_notional=stake_notional,
        quantity=quantity,
        capped=fractional_kelly_fraction > cap_fraction,
    )


def _binary_yes_kelly_fraction(probability: float, price: float) -> float:
    if probability <= price or price <= 0.0 or price >= 1.0:
        return 0.0
    return (probability - price) / (1.0 - price)


def _probability(value: float) -> float:
    probability = float(value)
    if probability < 0.0 or probability > 1.0:
        raise ValueError("predicted_prob must be between 0 and 1")
    return probability


def _price(value: Decimal) -> Decimal:
    price = _money(value)
    if price <= 0 or price >= 1:
        raise ValueError("price must be between 0 and 1")
    return price


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
