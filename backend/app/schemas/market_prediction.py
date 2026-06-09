from pydantic import BaseModel


class MarketPredictionResponse(BaseModel):
    slug: str
    predicted_prob: float
    confidence: float
    edge: float
    is_edge: bool
    reason: str
    provisional: bool
    paper_trading_only: bool = True
