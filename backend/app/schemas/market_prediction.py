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
    """Model read for one market.

    Loop117: ``available`` is False (with null ``predicted_prob``/``edge``) when
    the market has no stored price and no logged forecast — the honest shape for
    "no prediction available", served as a 200 instead of a 404.
    """

    slug: str
    available: bool = True
    predicted_prob: Optional[float] = None
    confidence: float
    edge: Optional[float] = None
    is_edge: bool
    reason: str
    provisional: bool
    # The market-implied YES the edge was computed against — the same price
    # /markets, /prices/latest and /candles serve for this slug (D5).
    market_implied: Optional[float] = None
    price_source: str = "unavailable"
    paper_trading_only: bool = True
    ensemble: Optional[EnsembleForecast] = None
