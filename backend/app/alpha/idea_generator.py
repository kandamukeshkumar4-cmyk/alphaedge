"""Deterministic proposal-only source for alpha research hypotheses.

The idea generator is a maker, never a checker.  It emits structured research
tickets only; :mod:`app.alpha.validator` remains solely responsible for any
validation verdict.  It deliberately has no order-path imports and no edge,
stake, or side fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FactorHypothesis:
    """A proposal to be tested by the independent deterministic validator."""

    name: str
    description: str
    required_inputs: tuple[str, ...]
    predicted_direction: str

    def to_dict(self) -> dict[str, Any]:
        """Return the public, JSON-safe research-ticket contract."""
        return asdict(self) | {"required_inputs": list(self.required_inputs)}


@dataclass(frozen=True)
class _SignalFamily:
    required_inputs: tuple[str, ...]
    predicted_direction: str
    description: str
    transforms: tuple[str, ...]
    windows: tuple[str, ...]


# These are research-ticket dimensions, not factor implementations.  The
# validator decides whether the corresponding captured source family warrants
# further research; no candidate is installed into FACTOR_FUNCTIONS here.
_SIGNAL_FAMILIES: dict[str, _SignalFamily] = {
    "model_edge": _SignalFamily(
        ("model_probability", "market_implied_probability"),
        "positive",
        "Model-market divergence may persist after normalizing recent observations.",
        ("normalized", "ranked"),
        ("6h", "24h"),
    ),
    "whale_flow": _SignalFamily(
        ("whale_flow",),
        "positive",
        "Sustained signed whale pressure may precede a market repricing.",
        ("rolling_mean", "rolling_sum"),
        ("1h", "6h"),
    ),
    "momentum": _SignalFamily(
        ("price_history",),
        "positive",
        "Recent price movement may continue over a bounded observation window.",
        ("difference", "return"),
        ("1h", "6h"),
    ),
    "mean_reversion": _SignalFamily(
        ("price_history",),
        "negative",
        "An extreme recent price displacement may revert toward its local mean.",
        ("deviation", "zscore"),
        ("6h", "24h"),
    ),
    "news_sentiment": _SignalFamily(
        ("news_signal", "sentiment_debate"),
        "positive",
        "Aligned news and debate sentiment may precede a favorable repricing.",
        ("average", "agreement"),
        ("6h", "24h"),
    ),
    "time_decay": _SignalFamily(
        ("edge", "hours_to_lock"),
        "positive",
        "A captured edge may strengthen as the market approaches its lock time.",
        ("discounted", "bucketed"),
        ("6h", "24h"),
    ),
    "cross_venue": _SignalFamily(
        ("polymarket_probability", "kalshi_probability"),
        "positive",
        "A mirrored-venue probability spread may close over a bounded window.",
        ("spread", "normalized"),
        ("1h", "6h"),
    ),
}


def propose_hypotheses(context: Mapping[str, object] | None = None) -> list[FactorHypothesis]:
    """Propose novel deterministic tickets, excluding known state-history names.

    ``context`` can carry ``validated_factors``, ``seen_hypotheses``, and
    ``rejected_hypotheses`` iterables.  Callers populate those sets from the
    persisted alpha-run history, keeping the last-30-day rejection memory out
    of this proposal-only module.
    """
    context = context or {}
    excluded = _names_from_context(context, "validated_factors")
    excluded.update(_names_from_context(context, "seen_hypotheses"))
    excluded.update(_names_from_context(context, "rejected_hypotheses"))
    proposals: list[FactorHypothesis] = []
    for family_name, family in _SIGNAL_FAMILIES.items():
        for transform in family.transforms:
            for window in family.windows:
                name = f"{family_name}__{transform}__{window}"
                if name in excluded:
                    continue
                proposals.append(
                    FactorHypothesis(
                        name=name,
                        description=f"{family.description} Transform: {transform}; window: {window}.",
                        required_inputs=family.required_inputs,
                        predicted_direction=family.predicted_direction,
                    )
                )
    return proposals


def source_factor_for(hypothesis_name: str) -> str | None:
    """Recover the existing signal family that the validator can evaluate."""
    family, separator, _details = hypothesis_name.partition("__")
    return family if separator and family in _SIGNAL_FAMILIES else None


def _names_from_context(context: Mapping[str, object], key: str) -> set[str]:
    value = context.get(key, ())
    if isinstance(value, (str, bytes)):
        return {value}
    try:
        return {str(item) for item in value}  # type: ignore[union-attr]
    except TypeError:
        return set()
