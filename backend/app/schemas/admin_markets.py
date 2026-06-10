from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db.models import MarketStatus


class AdminMarketListItem(BaseModel):
    slug: str
    title: str
    status: MarketStatus
    category: str
    tournament_tag: str | None = None

    model_config = {"from_attributes": True}


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
