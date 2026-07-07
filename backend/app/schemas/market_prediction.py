from typing import Optional

from pydantic import BaseModel


class EnsembleMemberEstimate(BaseModel):
    provider: str
    prob: float
    rationale: str = ""


class EnsembleForecast(BaseModel):
    """LLM-ensemble probability with disagreement-as-uncertainty.

    Separate from the XGBoost judge (predicted_prob): this aggregates the
    configured LLM providers. Present only when ENSEMBLE_ENABLED and at least
    one provider answered; otherwise the response omits it and the caller sees
    the exact single-model baseline.
    """

    prob: float
    stdev: float
    n_models: int
    spread_flag: bool
    per_model: list[EnsembleMemberEstimate] = []


class MarketPredictionResponse(BaseModel):
    slug: str
    predicted_prob: float
    confidence: float
    edge: float
    is_edge: bool
    reason: str
    provisional: bool
    paper_trading_only: bool = True
    ensemble: Optional[EnsembleForecast] = None
