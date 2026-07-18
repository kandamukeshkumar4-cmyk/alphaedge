"""v2-style alpha ensemble for prediction-market forecasts.

Adapted from virattt/ai-hedge-fund v2 (MIT, see docs/ATTRIBUTIONS.md):
the ``AlphaModel -> Signal`` interface, abstention semantics, and
conviction-weighted blending, re-targeted from equity tickers to
prediction-market YES-probabilities. LLM/agent code never touches the
order path; this package only shapes the forecast probability.
"""

from app.forecasting.alpha.base import AlphaModel, AlphaSignal
from app.forecasting.alpha.blend import BlendResult, blend_market_probability, blend_signals
from app.forecasting.alpha.spec import (
    ALPHA_MODEL_REGISTRY,
    BlendModelSpec,
    BlendSpec,
    default_blend_spec,
    load_blend_spec,
)

__all__ = [
    "ALPHA_MODEL_REGISTRY",
    "AlphaModel",
    "AlphaSignal",
    "BlendModelSpec",
    "BlendResult",
    "BlendSpec",
    "blend_market_probability",
    "blend_signals",
    "default_blend_spec",
    "load_blend_spec",
]
