"""Pydantic schemas for U12 observability endpoints.

No order-path imports.  No fabricated numbers — every field maps to a real
metric or is explicitly None/unavailable when the data is absent.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Agent-run trace explorer
# ---------------------------------------------------------------------------


class AgentRunStepOut(BaseModel):
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    # Wall-clock timestamp of the step record (ISO string).
    created_at: str


class AgentRunOut(BaseModel):
    run_id: str
    market_slug: str
    status: str  # "approved" | "blocked"
    graph_version: str
    created_at: str  # ISO timestamp
    steps: list[AgentRunStepOut]


class TraceExplorerOut(BaseModel):
    runs: list[AgentRunOut]
    total: int


# ---------------------------------------------------------------------------
# Calibration drift
# ---------------------------------------------------------------------------


class DriftOut(BaseModel):
    rolling_brier: Optional[float]
    baseline_brier: float
    drift: Optional[float]
    n_claims: int
    alarm: bool
    insufficient_data: bool
    threshold: float
    # History points for the drift chart: list of {window_days, brier}
    history: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Latency SLO tiles (sourced from Prometheus via /metrics text, parsed in
# the frontend; this endpoint provides a JSON summary for convenience)
# ---------------------------------------------------------------------------


class LatencySloTileOut(BaseModel):
    """One SLO tile: name, unit, p50/p95/p99, and whether the SLO is met."""

    name: str
    unit: str  # "ms"
    # None = no data observed yet (honest unavailable state)
    p50: Optional[float]
    p95: Optional[float]
    p99: Optional[float]
    slo_ms: float  # the target threshold
    slo_met: Optional[bool]  # None = insufficient data


class SloTilesOut(BaseModel):
    tiles: list[LatencySloTileOut]


# ---------------------------------------------------------------------------
# Combined observability summary (top-level)
# ---------------------------------------------------------------------------


class ObservabilitySummaryOut(BaseModel):
    drift: DriftOut
    slo_tiles: SloTilesOut
    paper_trading_only: bool = True
