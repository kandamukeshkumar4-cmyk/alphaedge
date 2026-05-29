from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import MarketStatus, OrderOutcome, OrderSide, OrderType


class MarketCreate(BaseModel):
    slug: str
    title: str
    question: str
    lock_at: Optional[datetime] = None


class MarketResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    question: str
    status: MarketStatus
    lock_at: Optional[datetime]
    resolved_at: Optional[datetime]
    winning_outcome: Optional[OrderOutcome]

    model_config = {"from_attributes": True}


class MarketResolve(BaseModel):
    winning_outcome: OrderOutcome


class OrderCreate(BaseModel):
    account_id: UUID
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    price: Optional[Decimal] = Field(default=None, ge=0.01, le=0.99)


class OrderResponse(BaseModel):
    id: UUID
    market_id: UUID
    account_id: UUID
    side: OrderSide
    outcome: OrderOutcome
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    status: str

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    market_id: UUID
    yes_shares: Decimal
    no_shares: Decimal
    avg_yes_cost: Decimal
    avg_no_cost: Decimal

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    paper_trading_only: bool
    disclaimer: str
