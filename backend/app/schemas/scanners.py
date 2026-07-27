"""Contracts for Scanner Studio alert scanners (research-only)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CompileAnswerIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=0, max_length=500)


class ScannerCompileRequest(BaseModel):
    """Loop 116 conversational compile. ``prompt`` is canonical; ``text`` is
    kept as a backward-compatible alias for one-shot clients.
    """

    prompt: str | None = Field(default=None, max_length=4000)
    text: str | None = Field(default=None, max_length=4000)
    answers: list[CompileAnswerIn] | None = None
    draft_id: str | None = Field(default=None, max_length=64)

    def resolved_prompt(self) -> str:
        if self.prompt is not None:
            return self.prompt
        if self.text is not None:
            return self.text
        return ""


class ClarifyQuestionOut(BaseModel):
    id: str
    question: str
    kind: Literal["schedule", "threshold", "universe", "delivery", "other"]
    suggestions: list[str] = Field(default_factory=list)


class ScannerCompileOut(BaseModel):
    """Ready or needs_clarification. One-shot clients still read ``spec`` /
    ``compiler`` / ``warnings`` when status is ready (and may see ``spec``
    mirrored from ``spec_partial`` during clarification for soft back-compat).
    """

    status: Literal["ready", "needs_clarification"] = "ready"
    draft_id: str | None = None
    spec: dict[str, Any] | None = None
    spec_partial: dict[str, Any] | None = None
    questions: list[ClarifyQuestionOut] = Field(default_factory=list)
    compiler: Literal["deterministic", "llm-assisted"] = "deterministic"
    warnings: list[str] = Field(default_factory=list)


class ScannerTestfireRequest(BaseModel):
    draft_id: str = Field(min_length=1, max_length=64)


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


class ScannerTestfireOut(BaseModel):
    """POST /scanners/compile/testfire — dry-run via real executor (is_test)."""

    draft_id: str
    run: ScannerRunOut
    summary: dict[str, Any]
    top_matches: list[dict[str, Any]] = Field(default_factory=list)


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


class ScannerFeatureRequest(BaseModel):
    is_featured: bool


class ScannerFeaturedListOut(BaseModel):
    items: list[ScannerOut]


class ScannerTrendingListOut(BaseModel):
    items: list[ScannerTrendingOut]
