"""Pydantic schemas for the agent-trace endpoint (U03 + U09)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class AgentTraceStepOut(BaseModel):
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]


class SimilarEventOut(BaseModel):
    """U09: a retrieved resolved-market precedent.

    All fields are populated from real resolved markets only. The endpoint
    omits this list when RETRIEVAL_ENABLED=false or no above-threshold
    candidates are found (honest empty state, no fabricated precedents).
    """

    slug: str
    title: str
    category: str
    outcome: str  # "YES" | "NO" | "unknown"
    similarity_score: float  # deterministic 0–1
    model_error_pts: Optional[float]  # None = no prediction log
    model_note: str  # e.g. "model was 6 pts under"
    resolved_at_iso: str  # ISO date string or ""
    market_url_path: str  # "/markets/{slug}"


class AgentTraceOut(BaseModel):
    slug: str
    verdict: str  # "BET" | "PASS" | "NO-EDGE"
    provisional: bool
    approved: bool
    reasoning: str
    steps: list[AgentTraceStepOut]
    paper_trading_only: bool = True
    # U09: populated when RETRIEVAL_ENABLED=true AND above-threshold matches exist.
    # Empty list (not null) when flag is OFF or no matches found.
    similar_events: list[SimilarEventOut] = []
