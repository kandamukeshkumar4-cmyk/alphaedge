"""Research-only inverse-volatility factor weighting.

This module produces a descriptive weight vector from realized research
returns.  It has no execution-path imports and cannot create paper orders.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence


MIN_RETURN_OBSERVATIONS = 8


def construct_research_weights(
    factor_returns: Mapping[str, Mapping[str, float]]
) -> dict[str, object]:
    """Return inverse-volatility weights over surviving factor research returns."""
    clean = {
        name: {key: float(value) for key, value in returns.items() if math.isfinite(float(value))}
        for name, returns in factor_returns.items()
    }
    common_ids = sorted(set.intersection(*(set(values) for values in clean.values()))) if clean else []
    if len(common_ids) < MIN_RETURN_OBSERVATIONS:
        return _reject("insufficient_common_oos_returns", common_ids)
    volatilities = {
        name: _sample_volatility([returns[item] for item in common_ids])
        for name, returns in clean.items()
    }
    if any(value <= 1e-12 for value in volatilities.values()):
        return _reject("zero_factor_return_volatility", common_ids, volatilities)
    inverse = {name: 1.0 / value for name, value in volatilities.items()}
    normalizer = math.fsum(inverse.values())
    weights = {name: inverse[name] / normalizer for name in sorted(inverse)}
    combined = {
        item: math.fsum(weights[name] * clean[name][item] for name in sorted(weights))
        for item in common_ids
    }
    return {
        "constructed": True,
        "reason": None,
        "weights": {name: round(value, 8) for name, value in weights.items()},
        "volatilities": {name: round(volatilities[name], 8) for name in sorted(volatilities)},
        "observation_ids": common_ids,
        "combined_returns": combined,
        "paper_trading_only": True,
    }


def _reject(
    reason: str, observation_ids: Sequence[str], volatilities: Mapping[str, float] | None = None
) -> dict[str, object]:
    return {
        "constructed": False,
        "reason": reason,
        "weights": {},
        "volatilities": dict(volatilities or {}),
        "observation_ids": list(observation_ids),
        "combined_returns": {},
        "paper_trading_only": True,
    }


def _sample_volatility(values: Sequence[float]) -> float:
    mean = math.fsum(values) / len(values)
    return math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1))
