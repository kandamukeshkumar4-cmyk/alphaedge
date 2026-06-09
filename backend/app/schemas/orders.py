from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PaperOrderCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    side: Literal["YES", "NO"]
    shares: float = Field(gt=0)
    price: float = Field(ge=0.01, le=0.99)


class PaperOrderResponse(BaseModel):
    order_id: UUID
    slug: str
    side: Literal["YES", "NO"]
    shares: float
    cost: float
    remaining_balance: float
    paper_trading_only: bool = True
