from typing import Optional

from pydantic import BaseModel, Field


class NewsSignalItem(BaseModel):
    headline: str = ""
    sentiment_score: float = 0.0
    volume_score: float = 0.0
    sources_count: int = 0


class MarketExplainerResponse(BaseModel):
    """Model-vs-market explanation for one market.

    Loop117: ``available`` is False (with null probabilities) when the market
    has no stored price and no logged forecast — the honest shape for "no
    prediction available", served as a 200 instead of a 404.
    """

    slug: str
    available: bool = True
    model_prob: Optional[float] = None
    market_implied: Optional[float] = None
    edge: Optional[float] = None
    edge_direction: str
    confidence_label: str
    news_signals: list[NewsSignalItem] = Field(default_factory=list)
    trade_rationale: str
    provisional: bool
    explanation: str = ""
    model_used: str = "deterministic"
    # Which store ``market_implied`` came from — see services/market_lookup.py.
    price_source: str = "unavailable"
    paper_trading_only: bool = True
