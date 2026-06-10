from pydantic import BaseModel, Field


PORTFOLIO_DISCLAIMER = (
    "Research only — not financial advice. Verify resolution terms. Paper trading only."
)


class PortfolioPositionResponse(BaseModel):
    id: str | None = None
    market_slug: str
    side: str
    outcome: str = "yes"
    market_title: str = ""
    shares: float
    avg_cost: float
    cost: float
    realized_pnl: float | None = None
    settled: bool = False
    current_price: float | None = None
    unrealized_pnl: float | None = None
    pnl_pct: float | None = None


class PortfolioResponse(BaseModel):
    paper_balance: float
    positions: list[PortfolioPositionResponse] = Field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    portfolio_value: float = 0.0
    total_trades: int = 0
    paper_trading_only: bool = True
    disclaimer: str = PORTFOLIO_DISCLAIMER
