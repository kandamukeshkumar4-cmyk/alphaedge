from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TrackRecordCalibrationBin(BaseModel):
    lower: float
    upper: float
    count: int
    mean_predicted: float | None
    observed_frequency: float | None


class TrackRecordBrierPoint(BaseModel):
    seq: int
    scored_at: datetime | None
    brier: float
    cumulative_brier: float


class TrackRecordClvBucket(BaseModel):
    # None lower/upper mark the open-ended overflow buckets.
    lower: float | None
    upper: float | None
    count: int


class TrackRecordClvSummary(BaseModel):
    count: int
    mean: float | None
    min: float | None
    max: float | None
    positive_share: float | None
    histogram: list[TrackRecordClvBucket]


class TrackRecordResponse(BaseModel):
    n: int
    thin_data: bool
    thin_data_threshold: int
    brier_score: float | None
    calibration_bins: list[TrackRecordCalibrationBin]
    brier_over_time: list[TrackRecordBrierPoint]
    clv: TrackRecordClvSummary
    source: Literal["forecast_scores", "paper_orders", "none"]
    last_updated: datetime | None
    paper_trading_only: bool = True
    disclaimer: str
