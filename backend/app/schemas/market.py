from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.db.models import MarketStatus, OrderOutcome, OrderSide, OrderStatus, OrderType


class MarketCreate(BaseModel):
    slug: str
    title: str
    question: str
    lock_at: Optional[datetime] = None
    category: str = "Sports"
    icon: str = "basketball"
    volume: int = 0
    traders: int = 0
    market_count: int = 1
    description: str = ""
    resolution: str = ""


class MarketResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    question: str
    category: str = "Sports"
    icon: str = "basketball"
    volume: int = 0
    traders: int = 0
    market_count: int = 1
    description: str = ""
    resolution: str = ""
    status: MarketStatus
    lock_at: Optional[datetime]
    resolved_at: Optional[datetime]
    winning_outcome: Optional[OrderOutcome]
    resolution_outcome: Optional[str] = None
    source: str = "seed"
    image_url: Optional[str] = None
    yes_price: Optional[float] = None

    model_config = {"from_attributes": True}


class BookLevel(BaseModel):
    price: float
    size: float


class OutcomeBookSnapshot(BaseModel):
    bids: list[BookLevel]
    asks: list[BookLevel]


class OrderBookSnapshot(BaseModel):
    yes: OutcomeBookSnapshot
    no: OutcomeBookSnapshot


class MarketActivityItem(BaseModel):
    id: UUID
    outcome: OrderOutcome
    price: float
    quantity: float
    created_at: datetime


class MarketForecastSnapshot(BaseModel):
    predicted_prob: float
    confidence: float
    edge_vs_book: Optional[float]
    input_feature_hash: Optional[str]


class MarketEvaluationSnapshot(BaseModel):
    latest_brier_score: float
    predicted_prob: Optional[float]
    actual_outcome: int
    closing_implied: Optional[float]


class MarketSnapshotResponse(BaseModel):
    paper_trading_only: bool
    disclaimer: str
    market: MarketResponse
    book: OrderBookSnapshot
    activity: list[MarketActivityItem]
    forecast: Optional[MarketForecastSnapshot]
    evaluation: Optional[MarketEvaluationSnapshot]


class MarketResolve(BaseModel):
    winning_outcome: OrderOutcome


class OrderRiskInput(BaseModel):
    predicted_prob: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    edge: float
    current_drawdown: float = Field(default=0, ge=0)
    minutes_before_start: int = Field(ge=0)


class OrderCreate(BaseModel):
    account_id: UUID
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    price: Optional[Decimal] = Field(default=None, ge=0.01, le=0.99)
    expires_at: Optional[datetime] = None
    risk: OrderRiskInput


class OrderCancelRequest(BaseModel):
    account_id: UUID


class PaperSignalCreate(BaseModel):
    account_id: UUID
    outcome: OrderOutcome


class PaperSignalOption(BaseModel):
    outcome: OrderOutcome
    count: int
    percentage: float


class PaperSignalSummaryResponse(BaseModel):
    paper_trading_only: bool
    market_id: UUID
    market_slug: str
    selected_outcome: Optional[OrderOutcome]
    total_signals: int
    options: list[PaperSignalOption]


class AgentRunStepResponse(BaseModel):
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]

    model_config = {"from_attributes": True}


class AgentRunResponse(BaseModel):
    run_id: UUID
    market_id: UUID
    market_slug: str
    market_title: str
    status: str
    graph_version: str
    approved: bool
    predicted_prob: float
    confidence: float
    reasoning: str
    errors: list[str]
    created_at: datetime
    steps: list[AgentRunStepResponse]
    disclaimer: str


class AgentRunSummaryResponse(BaseModel):
    run_id: UUID
    market_id: UUID
    market_slug: str
    market_title: str
    status: str
    graph_version: str
    approved: bool
    step_count: int
    errors: list[str]
    created_at: datetime


class AgentRunListResponse(BaseModel):
    disclaimer: str
    runs: list[AgentRunSummaryResponse]


class MarketSnapshotCaptureFailureResponse(BaseModel):
    source: str
    target: str
    error: str


class MarketSnapshotCaptureRunResponse(BaseModel):
    run_id: UUID
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    fetched: int
    ingested: int
    skipped: int
    failed: int
    failures: list[MarketSnapshotCaptureFailureResponse]
    captured_at: Optional[datetime] = None


class MarketSnapshotCaptureRunListResponse(BaseModel):
    runs: list[MarketSnapshotCaptureRunResponse]


class Phase3SnapshotStoreBacktestRequest(BaseModel):
    """Body for POST /admin/phase3-snapshot-store-backtests (SEC-Z1-01).

    Requires an explicit source so empty ``{}`` fails validation with 422
    instead of reaching the empty-store KeyError path.
    """

    source: str = Field(
        ...,
        description="Must be 'snapshot_store' (resolved odds feature matrix).",
        min_length=1,
    )


class Phase3SnapshotStoreBacktestRunResponse(BaseModel):
    run_id: UUID
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    market_count: int
    phase3_gate: str
    is_edge: bool
    blocked_reasons: list[str]
    sample_shortfall: int
    walk_forward_count: int
    model_brier: float
    closing_brier: float
    mean_clv: float
    clv_positive: bool
    walk_forward: dict[str, Any]
    edge_gate: dict[str, Any]
    calibration: dict[str, Any]


class Phase3SnapshotStoreBacktestRunListResponse(BaseModel):
    runs: list[Phase3SnapshotStoreBacktestRunResponse]


class OrderResponse(BaseModel):
    id: UUID
    market_id: UUID
    account_id: UUID
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    status: str
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_serializer("expires_at")
    def serialize_expires_at(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()


class OrderFillBreakdownResponse(BaseModel):
    id: UUID
    price: Decimal
    quantity: Decimal
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        else:
            value = value.astimezone(UTC)
        return value.isoformat()


class OrderHistoryItemResponse(BaseModel):
    id: UUID
    market_id: UUID
    market_slug: str
    market_title: str
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    filled_notional: Decimal
    average_fill_price: Optional[Decimal]
    status: OrderStatus
    expires_at: Optional[datetime]
    created_at: datetime
    fills: list[OrderFillBreakdownResponse]

    @field_serializer("expires_at", "created_at")
    def serialize_timestamps(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        else:
            value = value.astimezone(UTC)
        return value.isoformat()


class OrderHistoryPageResponse(BaseModel):
    items: list[OrderHistoryItemResponse]
    next_cursor: Optional[str]


class PositionResponse(BaseModel):
    market_id: UUID
    yes_shares: Decimal
    no_shares: Decimal
    avg_yes_cost: Decimal
    avg_no_cost: Decimal

    model_config = {"from_attributes": True}


class OpenOrderResponse(BaseModel):
    id: UUID
    market_id: UUID
    market_slug: str
    market_title: str
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    reserved_notional: Decimal
    status: OrderStatus


class AccountOrderHistoryResponse(BaseModel):
    id: UUID
    market_id: UUID
    market_slug: str
    market_title: str
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    filled_notional: Decimal
    average_fill_price: Optional[Decimal]
    status: OrderStatus
    created_at: datetime


class PaperAccountResponse(BaseModel):
    id: UUID
    name: str
    cash_balance: Decimal
    reserved_cash: Decimal
    available_cash: Decimal
    paper_trading_only: bool
    positions: list[PositionResponse]
    open_orders: list[OpenOrderResponse]
    order_history: list[AccountOrderHistoryResponse]

    model_config = {"from_attributes": True}


class MarketDetailOutcome(BaseModel):
    label: str
    implied_prob: float
    price: float


class MarketDetailForecast(BaseModel):
    model_prob: float
    clv_gate_passed: bool
    provisional: bool


class MarketDetailResponse(BaseModel):
    slug: str
    title: str
    category: str
    status: str
    outcomes: list[MarketDetailOutcome]
    forecast: Optional[MarketDetailForecast] = None
    volume_usd: int
    traders: int
    resolution_criteria: str
    paper_trading_only: bool = True
    resolved: bool = False
    resolution_outcome: Optional[str] = None
    winning_outcome: Optional[str] = None
    resolved_at: Optional[datetime] = None
    watching_count: int = 0


class HealthResponse(BaseModel):
    status: str
    paper_trading_only: bool
    disclaimer: str


class UnifiedMarketSearchResult(BaseModel):
    """
    Unified cross-platform market search result.

    Shape inspired by pmxt (MIT) UnifiedMarket model
    (vendor-study/pmxt-dev__pmxt/sdks/python/pmxt/models.py).
    Attribution: pmxt-dev/pmxt, MIT License.
    See docs/ATTRIBUTIONS.md.
    """

    slug: str
    title: str
    platform: str  # "Polymarket" | "Kalshi" | "AlphaEdge"
    category: str
    market_type: str = "prediction"
    yes_price: Optional[float] = None
    volume: int = 0
    status: str = "open"  # "open" | "locked" | "resolved"
