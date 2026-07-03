"""Public API response schemas (T12) — the UI-loop contract."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClaimOut(BaseModel):
    direction: str
    horizon_minutes: int
    confidence: float
    status: str
    price_at_claim: Optional[float] = None
    resolution_price: Optional[float] = None
    resolved_at: Optional[datetime] = None


class BriefOut(BaseModel):
    id: str
    market_slug: str
    kind: str
    headline: str
    body_markdown: str
    citations: list[dict]
    generator: str
    model_version: str
    prompt_version: str
    created_at: datetime
    claim: Optional[ClaimOut] = None


class BriefListOut(BaseModel):
    items: list[BriefOut]
    total: int
    limit: int
    offset: int


class AggregateOut(BaseModel):
    dimension: str
    dim_key: str
    window_days: int
    n: int
    accuracy: float
    brier: float
    provisional: bool
    computed_at: Optional[datetime] = None


class TrackRecordOut(BaseModel):
    aggregates: list[AggregateOut]


class GradedClaimOut(BaseModel):
    market_slug: str
    direction: str
    horizon_minutes: int
    confidence: float
    status: str
    price_at_claim: Optional[float] = None
    resolution_price: Optional[float] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime


class ClaimListOut(BaseModel):
    items: list[GradedClaimOut]
    total: int
    limit: int
    offset: int


class LatencyOut(BaseModel):
    market_slug: str
    last_snapshot_at: Optional[datetime] = None
    staleness_seconds: Optional[float] = None
    source: Optional[str] = None
    live: bool = False
