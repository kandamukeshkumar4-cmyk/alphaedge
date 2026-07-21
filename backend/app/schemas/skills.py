"""Contracts for the skills library (saved research step-plan templates)."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    icon: str | None = Field(default=None, max_length=16)
    template: list[Any] = Field(min_length=1)
    params_schema: dict[str, Any] | list[Any] | None = None
    is_public: bool = True


class SkillOut(BaseModel):
    id: UUID
    name: str
    description: str
    icon: str | None
    template: list[Any]
    params_schema: dict[str, Any] | list[Any] | None
    run_count: int
    is_public: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class SkillRunRequest(BaseModel):
    market_slug: str = Field(min_length=1, max_length=128)
    question: str | None = Field(default=None, min_length=1, max_length=4000)
    params: dict[str, Any] | None = None


class SkillRunOut(BaseModel):
    session_id: UUID
