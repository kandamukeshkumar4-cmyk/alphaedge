from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PaperOrderCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    side: Literal["buy", "YES", "NO"]
    outcome: Literal["yes", "no"] | None = None
    shares: float = Field(gt=0)
    price: float = Field(ge=0.01, le=0.99)

    @model_validator(mode="after")
    def normalize_legacy_side(self) -> "PaperOrderCreate":
        if self.side in ("YES", "NO"):
            object.__setattr__(self, "outcome", self.side.lower())  # type: ignore[arg-type]
            object.__setattr__(self, "side", "buy")
        if self.outcome is None:
            raise ValueError("outcome is required when side is buy")
        return self


class PaperOrderResponse(BaseModel):
    order_id: UUID
    slug: str
    side: Literal["YES", "NO"]
    shares: float
    cost: float
    remaining_balance: float
    paper_trading_only: bool = True


class PositionCloseRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    outcome: Literal["yes", "no"]
    shares: float = Field(gt=0)
    price: float = Field(ge=0.01, le=0.99)


class PositionCloseResponse(BaseModel):
    order_id: UUID
    slug: str
    outcome: Literal["yes", "no"]
    shares_sold: float
    proceeds: float
    realized_pnl: float
    remaining_shares: float
    remaining_balance: float
    paper_trading_only: bool = True


class PaperOrderHistoryItem(BaseModel):
    slug: str
    outcome: str
    side: str
    shares: float
    price: float
    cost: float
    action: str = "BUY"
    realized_pnl: float | None = None
    settled: bool
    created_at: datetime
