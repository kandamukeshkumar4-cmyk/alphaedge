from pydantic import BaseModel, Field


class DetailedHealthResponse(BaseModel):
    status: str
    paper_trading_only: bool = True
    checks: dict[str, str] = Field(default_factory=dict)
    version: str = "0.1.0"
