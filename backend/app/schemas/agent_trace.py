"""Pydantic schemas for the agent-trace endpoint (U03)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AgentTraceStepOut(BaseModel):
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]


class AgentTraceOut(BaseModel):
    slug: str
    verdict: str  # "BET" | "PASS" | "NO-EDGE"
    provisional: bool
    approved: bool
    reasoning: str
    steps: list[AgentTraceStepOut]
    paper_trading_only: bool = True
