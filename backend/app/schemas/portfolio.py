from pydantic import BaseModel, Field


PORTFOLIO_DISCLAIMER = (
    "Research only — not financial advice. Verify resolution terms. Paper trading only."
)

EXPOSURE_DISCLAIMER = (
    "Research only — not financial advice. "
    "Exposure figures are cost-basis notional, not mark-to-market. "
    "Paper trading only."
)


class ExposureGroupResponse(BaseModel):
    underlier: str
    position_count: int
    net_directional: float
    total_notional: float
    pct_of_total: float
    concentrated: bool
    positions: list[str] = Field(default_factory=list)


class ExposureResponse(BaseModel):
    total_open_notional: float = 0.0
    groups: list[ExposureGroupResponse] = Field(default_factory=list)
    has_concentration: bool = False
    concentrated_underliers: list[str] = Field(default_factory=list)
    paper_trading_only: bool = True
    disclaimer: str = EXPOSURE_DISCLAIMER


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
    settlement_status: str = "open"
    current_price: float | None = None
    unrealized_pnl: float | None = None
    pnl_pct: float | None = None


class PortfolioSummaryResponse(BaseModel):
    bankroll: float
    open_positions: int = 0
    total_invested: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


class PortfolioRiskResponse(BaseModel):
    """Risk metrics over the user's paper book (E12). Descriptive, not advice."""

    n_closed: int = 0
    total_realized_pnl: float = 0.0
    win_rate: float | None = None
    max_drawdown: float = 0.0
    sharpe: float | None = None  # per-trade, NOT annualized
    exposure_by_category: dict[str, float] = Field(default_factory=dict)
    exposure_pct_by_category: dict[str, float] = Field(default_factory=dict)
    paper_trading_only: bool = True
    disclaimer: str = PORTFOLIO_DISCLAIMER


class AttributionTradeResponse(BaseModel):
    order_id: str
    slug: str
    title: str
    category: str
    side: str
    cost: float
    realized_pnl: float
    created_at: str


class PortfolioAttributionResponse(BaseModel):
    """B2 — performance attribution over settled paper trades (no advice)."""

    win_rate: float | None = None
    roi: float = 0.0
    total_realized_pnl: float = 0.0
    total_cost: float = 0.0
    n_trades: int = 0
    top_trades: list[AttributionTradeResponse] = Field(default_factory=list)
    bottom_trades: list[AttributionTradeResponse] = Field(default_factory=list)
    monthly_pnl: dict[str, float] = Field(default_factory=dict)
    category_pnl: dict[str, float] = Field(default_factory=dict)
    paper_trading_only: bool = True
    disclaimer: str = PORTFOLIO_DISCLAIMER


class EquityCurvePoint(BaseModel):
    date: str
    cash_balance: float
    positions_mtm: float
    equity: float


class EquityCurveResponse(BaseModel):
    """B5 — historical daily equity curve from portfolio_equity_snapshots."""

    points: list[EquityCurvePoint] = Field(default_factory=list)
    paper_trading_only: bool = True
    disclaimer: str = PORTFOLIO_DISCLAIMER


class PortfolioResponse(BaseModel):
    paper_balance: float
    positions: list[PortfolioPositionResponse] = Field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    portfolio_value: float = 0.0
    total_trades: int = 0
    paper_trading_only: bool = True
    disclaimer: str = PORTFOLIO_DISCLAIMER
