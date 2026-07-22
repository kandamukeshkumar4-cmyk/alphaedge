"""Contracts for skill/scanner subscriptions (community layer)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    ref_type: Literal["skill", "scanner"]
    ref_id: UUID


class SubscriptionOut(BaseModel):
    ref_type: Literal["skill", "scanner"]
    ref_id: UUID
    name: str
    created_at: datetime
