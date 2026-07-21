"""Contracts for the authenticated, read-only research terminal."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ResearchSessionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    market_slug: str | None = Field(default=None, min_length=1, max_length=128)


class ResearchStepOut(BaseModel):
    id: UUID
    sequence: int
    title: str
    kind: Literal["table", "chart", "text"]
    status: str
    payload: dict[str, Any]
    citations: list[Any]
    created_at: datetime


class ResearchSessionOut(BaseModel):
    id: UUID
    question: str
    market_slug: str | None
    status: str
    summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    steps: list[ResearchStepOut] = Field(default_factory=list)
