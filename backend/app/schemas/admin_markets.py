from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.db.models import MarketStatus


class AdminMarketListItem(BaseModel):
    slug: str
    title: str
    status: MarketStatus
    category: str
    tournament_tag: str | None = None

    model_config = {"from_attributes": True}


class AdminMarketDetail(BaseModel):
    id: UUID
    slug: str
    title: str
    question: str
    status: MarketStatus
    category: str
    icon: str = "basketball"
    description: str = ""
    resolution: str = ""
    tournament_tag: str | None = None
    lock_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    paper_trading_only: bool = True

    model_config = {"from_attributes": True}


class AdminMarketCreateRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=128)
    title: str = Field(..., min_length=1, max_length=256)
    question: str = Field(..., min_length=1)
    category: str = Field(default="Sports", max_length=64)
    icon: str = Field(default="basketball", max_length=32)
    description: str = ""
    resolution: str = ""
    tournament_tag: str | None = Field(default=None, max_length=32)
    lock_at: datetime | None = None

    @field_validator("slug")
    @classmethod
    def slug_format(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned or " " in cleaned:
            raise ValueError("slug must be non-empty and contain no spaces")
        return cleaned

    @field_validator("title", "question")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class AdminMarketEditRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    question: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=64)
    icon: str | None = Field(default=None, max_length=32)
    description: str | None = None
    resolution: str | None = None
    tournament_tag: str | None = Field(default=None, max_length=32)
    lock_at: datetime | None = None


class AdminMarketActionResponse(BaseModel):
    slug: str
    status: MarketStatus
    paper_trading_only: bool = True


class AdminJobRunItem(BaseModel):
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class AdminJobRunListResponse(BaseModel):
    runs: list[AdminJobRunItem]


class ResolveMarketRequest(BaseModel):
    winning_outcome: Literal["YES", "NO", "VOID"] = Field(
        description="Resolved outcome for the market",
    )


class MarketResolveResponse(BaseModel):
    slug: str
    winning_outcome: str
    settled: int
    skipped_already_settled: int
    total_payout: str
    paper_orders_settled: int = 0
    paper_trading_only: bool = True
