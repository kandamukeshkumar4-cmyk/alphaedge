"""Pydantic schemas for the agent-trace endpoint (U03)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class AgentTraceStepOut(BaseModel):
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]


class AgentTraceOut(BaseModel):
    """Per-step agent trace for one market.

    Loop117: ``available`` is False (empty ``steps``) when the market has no
    stored price and no logged forecast — an honest 200, never a 404.
    """

    slug: str
    available: bool = True
    verdict: str  # "BET" | "PASS" | "NO-EDGE"
    provisional: bool
    approved: bool
    reasoning: str
    steps: list[AgentTraceStepOut]
    # Market-implied YES the graph ran against, and which store it came from.
    market_implied: Optional[float] = None
    price_source: str = "unavailable"
    paper_trading_only: bool = True
