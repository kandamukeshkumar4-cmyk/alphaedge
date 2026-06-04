from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import ExternalMarketStatus, ForecastMode, ForecastSource, Platform


class ForecasterCreateResponse(BaseModel):
    id: UUID
    token: str = Field(description="Raw token. Shown once; store it client-side to keep your history.")
    disclaimer: str


class RecoveryEmailRequest(BaseModel):
    token: str
    email: str


class ResolveUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None
    category: Optional[str] = None
    close_at: Optional[datetime] = None


class ExternalMarketResponse(BaseModel):
    id: UUID
    platform: Platform
    external_id: str
    url: str
    title: str
    category: str
    status: ExternalMarketStatus
    close_at: Optional[datetime]
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class BackfillMarketResponse(BaseModel):
    """A resolved market exposed for practice calibration. The outcome is
    deliberately hidden so practice forecasts are not leaked the answer."""

    id: UUID
    platform: Platform
    external_id: str
    url: str
    title: str
    category: str

    model_config = {"from_attributes": True}


class ForecastCreateRequest(BaseModel):
    token: str
    url: str
    user_probability: float = Field(ge=0.0, le=1.0, description="Your P(YES) belief.")
    market_implied_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    snapshot_source: str = "manual"
    outcome_label: str = "YES"
    snapshot_metadata: dict[str, object] = Field(default_factory=dict)
    market_title: Optional[str] = None
    category: Optional[str] = None
    close_at: Optional[datetime] = None
    mode: ForecastMode = ForecastMode.LIVE
    source: ForecastSource = ForecastSource.WEB


class ForecastResponse(BaseModel):
    id: UUID
    external_market_id: UUID
    seq: int
    platform: Platform
    market_url: str
    outcome_label: str
    user_probability: float
    market_implied_probability: Optional[float]
    snapshot_source: str
    snapshot_metadata: dict[str, object]
    is_independent: bool
    mode: ForecastMode
    source: ForecastSource
    time_to_resolution_seconds: Optional[int]
    locked_at: datetime
    disclaimer: str


class AdminResolveRequest(BaseModel):
    winning_outcome: int = Field(ge=0, le=1, description="1 = resolved YES, 0 = resolved NO.")
    resolved_at: Optional[datetime] = None


# ----- dashboard -----
class CalibrationBin(BaseModel):
    lower: float
    upper: float
    count: int
    mean_predicted: Optional[float]
    observed_frequency: Optional[float]


class CategoryEdge(BaseModel):
    category: str
    count: int
    mean_brier_delta: Optional[float]
    provisional: bool


class PlatformEdge(BaseModel):
    platform: Platform
    count: int
    mean_brier_delta: Optional[float]


class TimeBucketEdge(BaseModel):
    bucket: str
    count: int
    mean_brier_delta: Optional[float]


class BrierTrendPoint(BaseModel):
    seq: int
    locked_at: datetime
    user_brier: float
    market_brier: Optional[float]


class DashboardMetrics(BaseModel):
    resolved_count: int
    unresolved_count: int
    headline_count: int
    independent_count: int
    anchored_count: int
    mean_user_brier: Optional[float]
    mean_market_brier: Optional[float]
    mean_brier_delta: Optional[float]
    synthetic_pnl_total: float
    brier_provisional: bool
    calibration_provisional: bool


class PracticeMetrics(BaseModel):
    resolved_count: int
    mean_user_brier: Optional[float]
    mean_brier_delta: Optional[float]


class DashboardResponse(BaseModel):
    forecaster_id: UUID
    paper_trading_only: bool
    disclaimer: str
    live: DashboardMetrics
    practice: PracticeMetrics
    calibration: list[CalibrationBin]
    category_breakdown: list[CategoryEdge]
    platform_breakdown: list[PlatformEdge]
    time_breakdown: list[TimeBucketEdge]
    brier_trend: list[BrierTrendPoint]
