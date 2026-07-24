"""Contracts for Scanner Studio alert scanners (research-only)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ScannerCompileRequest(BaseModel):
    text: str = Field(min_length=0, max_length=4000)


class ScannerCompileOut(BaseModel):
    spec: dict[str, Any]
    compiler: Literal["deterministic", "llm-assisted"] = "deterministic"
    warnings: list[str] = Field(default_factory=list)


class ScannerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    spec: dict[str, Any]
    is_public: bool = False
    cooldown_minutes: int = Field(default=120, ge=0, le=10080)


class ScannerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    spec: dict[str, Any] | None = None
    is_public: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10080)


class ScannerRunOut(BaseModel):
    id: UUID
    scanner_id: UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    checkpoint: dict[str, Any] | None
    result: dict[str, Any] | None
    error: str | None
    duration_ms: int | None = None
    # loop86 F-B: True for pre-publish test-mode runs (never alerts/emails).
    is_test: bool = False
    # loop87 H3: healing visibility (API only — UI later).
    repairs_count: int = 0
    repairs: list[dict[str, Any]] = Field(default_factory=list)


class ScannerTestEmailOut(BaseModel):
    """Result of POST /scanners/{id}/test-email (loop86 F-B)."""

    sent: bool
    reason: str | None = None


class ScannerOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner: str | None
    spec: dict[str, Any]
    version: int
    status: str
    is_public: bool
    is_featured: bool = False
    cooldown_minutes: int
    created_at: datetime
    updated_at: datetime
    latest_run: ScannerRunOut | None = None
    next_run_at: datetime | None = None
    last_error: str | None = None


class ScannerRateRequest(BaseModel):
    stars: int = Field(ge=1, le=5)


class ScannerRatingOut(BaseModel):
    avg: float
    count: int
    my_stars: int


class ScannerTrendingOut(ScannerOut):
    avg_rating: float
    rating_count: int
    run_count: int
    trending_score: float


class ScannerFeaturedListOut(BaseModel):
    items: list[ScannerOut]


class ScannerTrendingListOut(BaseModel):
    items: list[ScannerTrendingOut]
