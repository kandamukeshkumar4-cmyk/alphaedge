"""Analyst brief schema (T07): a cited research brief with a falsifiable claim.

The claim is deterministic/structured (not free LLM text) so the eval harness (T08)
can grade it. Citations are required (>=1) — a brief with no evidence is invalid.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CitationKind(str, Enum):
    NEWS = "news"
    WALLET = "wallet"
    MODEL = "model"
    ORDERBOOK = "orderbook"
    PRICE = "price"  # diff-engine price trend / jump evidence


class ClaimDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    JUSTIFIED = "justified"
    OVERREACTION = "overreaction"


class Citation(BaseModel):
    kind: CitationKind
    ref: str = Field(min_length=1, max_length=512)
    url: Optional[str] = Field(default=None, max_length=1024)


class Claim(BaseModel):
    direction: ClaimDirection
    horizon_minutes: int = 60
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("horizon_minutes")
    @classmethod
    def _horizon_allowed(cls, v: int) -> int:
        if v not in (60, 1440):
            raise ValueError("horizon_minutes must be 60 or 1440")
        return v


class ToolUsage(BaseModel):
    """A market-data tool the agent graph invoked, with its key figures.

    Populated from the ``market_tools`` graph node's ``tools_used`` summary so the
    frontend can render what on-demand data informed the forecast.
    """

    tool: str = Field(min_length=1, max_length=64)
    spread: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    points: Optional[int] = None
    last: Optional[float] = None
    whale_count: Optional[int] = None
    error: Optional[str] = None


class AnalystBriefModel(BaseModel):
    market_slug: str = Field(min_length=1, max_length=128)
    trigger_event_id: Optional[str] = None
    headline: str = Field(min_length=1, max_length=120)
    body_markdown: str = Field(min_length=1, max_length=1200)
    citations: list[Citation]
    claim: Claim
    model_version: str = "unknown"
    prompt_version: str = "v1"
    generator: str = "llm"  # "llm" | "fallback"
    latency_ms: float = 0.0
    # Market-data tools that informed the forecast (from the market_tools node).
    tools_used: Optional[list[ToolUsage]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("citations")
    @classmethod
    def _at_least_one_citation(cls, v: list[Citation]) -> list[Citation]:
        if not v:
            raise ValueError("a brief must carry at least one citation")
        return v
