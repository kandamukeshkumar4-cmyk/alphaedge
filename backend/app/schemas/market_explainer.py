from pydantic import BaseModel


class MarketExplainerResponse(BaseModel):
    slug: str
    explanation: str
    model_used: str       # "claude-haiku-4-5" or "none"
    paper_trading_only: bool = True
