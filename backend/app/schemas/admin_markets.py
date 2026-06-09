from pydantic import BaseModel, Field


class MarketResolveRequest(BaseModel):
    outcome: str = Field(pattern="^(YES|NO)$")


class MarketResolveResponse(BaseModel):
    slug: str
    outcome: str
    positions_settled: int
    paper_trading_only: bool = True
