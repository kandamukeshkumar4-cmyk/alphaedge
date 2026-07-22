"""Contracts for the community market screener."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScreenerItem(BaseModel):
    slug: str
    title: str
    category: str
    icon: str
    volume: int
    yes_price: float | None
    move_24h: float | None
    model_edge: float | None
    hours_to_close: float | None


class ScreenerOut(BaseModel):
    items: list[ScreenerItem]
    total: int = Field(ge=0)
