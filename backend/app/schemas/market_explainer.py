from pydantic import BaseModel, Field


class NewsSignalItem(BaseModel):
    headline: str = ""
    sentiment_score: float = 0.0
    volume_score: float = 0.0
    sources_count: int = 0


class MarketExplainerResponse(BaseModel):
    slug: str
    model_prob: float
    market_implied: float
    edge: float
    edge_direction: str
    confidence_label: str
    news_signals: list[NewsSignalItem] = Field(default_factory=list)
    trade_rationale: str
    provisional: bool
    explanation: str = ""
    model_used: str = "deterministic"
    paper_trading_only: bool = True
