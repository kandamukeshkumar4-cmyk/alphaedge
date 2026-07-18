"""Blend alpha views into one probability — pure arithmetic, no I/O.

Adapted from virattt/ai-hedge-fund v2 ``portfolio/construction.py``:
per market, the blended conviction is a weighted mean over *voting* models,

    conviction = sum(w_m * value_m) / sum(w_m)

where an abstained signal is excluded from numerator AND denominator —
"no opinion" must not masquerade as "opinion: toss-up". A non-abstained
0.0 is a real toss-up vote and dilutes. Disagreement (weighted stddev of
the voting probabilities) is reported so callers can surface uncertainty.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.forecasting.alpha.base import AlphaSignal


class BlendResult(BaseModel):
    """The blended view and its decomposition."""

    model_config = ConfigDict(protected_namespaces=())

    probability: float = Field(ge=0.0, le=1.0)
    conviction: float = Field(ge=-1.0, le=1.0)
    disagreement: float = Field(ge=0.0, description="weighted stddev of voting probabilities")
    contributions: dict[str, float] = Field(
        default_factory=dict, description="model_name -> YES probability it voted"
    )
    weights: dict[str, float] = Field(
        default_factory=dict, description="model_name -> normalized blend weight"
    )
    abstained: list[str] = Field(default_factory=list)


def blend_signals(
    signals: list[AlphaSignal],
    model_weights: Mapping[str, float],
) -> BlendResult | None:
    """Blend one market's signals; ``None`` when every model abstains."""
    voting = [s for s in signals if not s.abstained]
    if not voting:
        return None

    total = 0.0
    weighted_value = 0.0
    for signal in voting:
        weight = float(model_weights[signal.model_name])
        if weight <= 0:
            raise ValueError(f"blend weight for {signal.model_name!r} must be > 0")
        total += weight
        weighted_value += weight * signal.value

    conviction = weighted_value / total
    probability = (conviction + 1.0) / 2.0

    variance = 0.0
    for signal in voting:
        weight = float(model_weights[signal.model_name]) / total
        variance += weight * (signal.probability - probability) ** 2

    return BlendResult(
        probability=probability,
        conviction=conviction,
        disagreement=math.sqrt(variance),
        contributions={s.model_name: s.probability for s in voting},
        weights={
            s.model_name: float(model_weights[s.model_name]) / total for s in voting
        },
        abstained=[s.model_name for s in signals if s.abstained],
    )


def blend_market_probability(
    features: Mapping[str, Any],
    *,
    artifact_probability: float | None = None,
) -> BlendResult | None:
    """Run the default blend spec over ``features``.

    ``artifact_probability`` is injected under the key the ``artifact``
    model reads, so callers that already computed the calibrated artifact
    probability (predict_market, the backtest replay) never recompute it.
    Returns ``None`` when every model abstains — callers keep their own
    probability unchanged in that case.
    """
    from app.forecasting.alpha.spec import default_blend_spec

    spec = default_blend_spec()
    enriched: dict[str, Any] = dict(features)
    if artifact_probability is not None:
        enriched["artifact_probability"] = artifact_probability

    signals = [model.predict(enriched) for model in spec.build_models()]
    return blend_signals(signals, spec.model_weights)
