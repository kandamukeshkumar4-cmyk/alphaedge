"""AlphaModel interface — every forecast view implements one contract.

Adapted from virattt/ai-hedge-fund v2 ``signals/base.py`` + ``models.py``:
an alpha model forms a *view* and nothing else; sizing, risk, and execution
stay in deterministic code elsewhere (here: RiskService -> OrderIntent ->
OrderBookService, which this package never calls).

The v2 convention is conviction in [-1, +1]. For a binary prediction market
the natural axis is the YES outcome: value = 2 * P(yes) - 1, so -1 means
"certain NO", 0 means "toss-up", +1 means "certain YES". Abstention is a
first-class state (metadata.abstained), distinct from a genuine 0.0 vote:
"no opinion" must not masquerade as "opinion: toss-up".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field


class AlphaSignal(BaseModel):
    """A view from one alpha model on one market."""

    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(description="which alpha model produced it")
    market_slug: str = ""
    value: float = Field(ge=-1.0, le=1.0, description="conviction toward YES in [-1, +1]")
    reasoning: str | None = None
    components: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def probability(self) -> float:
        """The YES-probability this conviction implies."""
        return (self.value + 1.0) / 2.0

    @property
    def abstained(self) -> bool:
        return self.metadata.get("abstained") is True

    @classmethod
    def from_probability(
        cls,
        model_name: str,
        probability: float,
        *,
        market_slug: str = "",
        reasoning: str | None = None,
    ) -> "AlphaSignal":
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        return cls(
            model_name=model_name,
            market_slug=market_slug,
            value=2.0 * probability - 1.0,
            reasoning=reasoning,
        )

    @classmethod
    def abstain(
        cls, model_name: str, reason: str, *, market_slug: str = ""
    ) -> "AlphaSignal":
        return cls(
            model_name=model_name,
            market_slug=market_slug,
            value=0.0,
            reasoning=reason,
            metadata={"abstained": True},
        )


class AlphaModel(ABC):
    """Abstract base: form a view on a market from its feature mapping.

    ``predict`` must be deterministic given ``features`` and must not
    perform I/O beyond reading already-loaded artifacts. Use
    ``AlphaSignal.abstain`` when the inputs required for a view are absent.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Model identifier, the key used in blend specs."""

    @abstractmethod
    def predict(self, features: Mapping[str, Any]) -> AlphaSignal:
        """Form a view on the market described by ``features``."""
