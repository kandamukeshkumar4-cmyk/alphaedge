"""Risk rules — all must pass before paper trade execution."""

from dataclasses import dataclass
from decimal import Decimal
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


class RiskService:
    MIN_EDGE = 0.05
    MIN_CONFIDENCE = 0.70
    MAX_DRAWDOWN = 0.15
    MAX_BET_PCT = 0.05

    def validate(self, intent: OrderIntent) -> tuple[bool, List[str]]:
        settings = get_settings()
        failures: List[str] = []

        if not settings.paper_trading_only:
            failures.append("PAPER_TRADING_ONLY must be true")
        if not intent.agent_enabled:
            failures.append("agent trading disabled")
        if intent.edge < self.MIN_EDGE:
            failures.append(f"edge {intent.edge:.2%} < {self.MIN_EDGE:.0%}")
        if intent.confidence < self.MIN_CONFIDENCE:
            failures.append(f"confidence {intent.confidence:.2f} < {self.MIN_CONFIDENCE}")
        if intent.current_drawdown >= self.MAX_DRAWDOWN:
            failures.append(f"drawdown {intent.current_drawdown:.2%} >= {self.MAX_DRAWDOWN:.0%}")
        bet_notional = (intent.price or Decimal("0.5")) * intent.quantity
        if bet_notional > intent.bankroll * Decimal(str(self.MAX_BET_PCT)):
            failures.append("bet exceeds max % bankroll")
        if intent.minutes_before_start < 5:
            failures.append("too close to game start")

        return len(failures) == 0, failures
