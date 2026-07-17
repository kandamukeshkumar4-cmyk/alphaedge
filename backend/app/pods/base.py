"""Pod contracts. Deliberately pure: no database or order-path imports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class PricePoint:
    captured_at: datetime
    implied_yes: Decimal


@dataclass(frozen=True)
class PodMarket:
    """Pre-close market data a pod is allowed to score.

    ``price_history`` must contain only observations captured before ``as_of``;
    the runner enforces that boundary before a pod receives this value.
    """

    market_id: str
    slug: str
    category: str
    price: Decimal
    close_at: object | None = None
    as_of: datetime | None = None
    price_history: tuple[PricePoint, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PodScore:
    value: int
    components: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ValueError("pod score must be in [0, 100]")


@dataclass(frozen=True)
class PodDecision:
    action: str
    outcome: str | None = None
    price: Decimal | None = None
    quantity: Decimal | None = None
    predicted_prob: float | None = None
    confidence: float | None = None
    edge: float | None = None
    reason: str = ""

    @property
    def is_entry(self) -> bool:
        return self.action == "enter"


class Pod(ABC):
    """A state-isolated paper strategy.

    Subclasses define a universe and pure score/decision functions. They never
    receive a database session and cannot bypass the validated order path.
    """

    key: str

    def __init__(self, *, config: Mapping[str, Any] | None = None) -> None:
        self.config = dict(config or {})

    @abstractmethod
    def universe(self) -> set[str]:
        """Return the allowed market categories/source labels for this pod."""

    @abstractmethod
    def score_market(self, market: PodMarket) -> PodScore:
        """Return a deterministic score from pre-close data only."""

    @abstractmethod
    def decide(self, market: PodMarket, score: PodScore) -> PodDecision:
        """Return a non-mutating decision; runner owns execution."""

    def size(self, *, bankroll: Decimal, price: Decimal) -> Decimal:
        """Bound a proposed stake to the configured fraction of pod bankroll."""
        max_fraction = Decimal(str(self.config.get("max_bet_fraction", "0.05")))
        if bankroll <= 0 or price <= 0 or max_fraction <= 0:
            return Decimal("0")
        return (bankroll * min(max_fraction, Decimal("0.05"))) / price
