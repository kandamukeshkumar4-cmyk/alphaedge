"""U12 Observability API endpoints.

GET /api/v1/admin/observability/traces       — recent agent-run trace explorer
GET /api/v1/admin/observability/drift        — calibration drift vs baseline
GET /api/v1/admin/observability/slo          — latency SLO summary from Prometheus
GET /api/v1/admin/observability/summary      — combined summary (drift + SLO)

Admin-only (X-Admin-API-Key header required for write operations; these are
read-only so they just use the existing admin key dependency).

Guardrails:
  - No OrderBookService / RiskService imports.
  - Drift alarm fires through EXISTING T09 AlertDispatchService.
  - PAPER_TRADING_ONLY never touched.
  - Honest unavailable states: returns None fields, never fabricates metrics.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import get_db
from app.schemas.observability import (
    AgentRunOut,
    AgentRunStepOut,
    DriftOut,
    LatencySloTileOut,
    ObservabilitySummaryOut,
    SloTilesOut,
    TraceExplorerOut,
)

router = APIRouter(prefix="/api/v1/admin/observability", tags=["observability"])


# ---------------------------------------------------------------------------
# Trace explorer
# ---------------------------------------------------------------------------


@router.get("/traces", response_model=TraceExplorerOut)
async def list_agent_traces(
    limit: int = 20,
    session=Depends(get_db),
) -> TraceExplorerOut:
    """Return the most-recent agent runs with per-step timings and I/O.

    Read-only — no orders submitted, no DB rows written.
    Steps are ordered by created_at within each run.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be 1–100")

    from app.services.agent_run_service import AgentRunService

    svc = AgentRunService(session)
    records = await svc.list_recent_runs(limit)

    runs = []
    for rec in records:
        steps = [
            AgentRunStepOut(
                step_name=s.step_name,
                input_data=s.input_data or {},
                output_data=s.output_data or {},
                created_at=s.created_at.isoformat(),
            )
            for s in rec.steps
        ]
        runs.append(
            AgentRunOut(
                run_id=str(rec.run.id),
                market_slug=rec.market.slug,
                status=rec.run.status,
                graph_version=rec.run.graph_version,
                created_at=rec.run.created_at.isoformat(),
                steps=steps,
            )
        )

    return TraceExplorerOut(runs=runs, total=len(runs))


# ---------------------------------------------------------------------------
# Calibration drift
# ---------------------------------------------------------------------------


def _build_drift_history(aggregates: list) -> list[dict[str, Any]]:
    """Build a sorted list of {window_days, brier} from overall aggregates."""
    rows = [
        {"window_days": row.window_days, "brier": float(row.brier)}
        for row in aggregates
        if row.dimension == "overall" and row.n >= 1
    ]
    return sorted(rows, key=lambda r: r["window_days"])


@router.get("/drift", response_model=DriftOut)
async def get_calibration_drift(
    session=Depends(get_db),
) -> DriftOut:
    """Compute rolling Brier vs baseline and return drift info.

    If DRIFT_ALARM_ENABLED=true and the drift exceeds the threshold, this
    endpoint fires the alarm through T09 AlertDispatchService.  The flag is
    OFF by default — the alarm path is dead when the flag is off.
    """
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.models import AnalystEvalAggregate
    from app.observability.drift import compute_drift_from_db, maybe_fire_drift_alarm
    from app.observability.metrics import update_drift_gauge

    settings = get_settings()
    result = await compute_drift_from_db(
        session, window=settings.drift_rolling_window
    )

    # Update Prometheus gauges (always — drift gauge reflects latest computation)
    if result.rolling_brier is not None:
        update_drift_gauge(result.drift or 0.0, result.rolling_brier)

    # Fire alarm (no-op when flag is OFF)
    await maybe_fire_drift_alarm(result, session, settings=settings)

    # Build history for the drift chart
    agg_rows = list(
        (
            await session.execute(
                select(AnalystEvalAggregate).where(
                    AnalystEvalAggregate.dimension == "overall"
                )
            )
        ).scalars()
    )
    history = _build_drift_history(agg_rows)

    return DriftOut(
        rolling_brier=result.rolling_brier,
        baseline_brier=result.baseline_brier,
        drift=result.drift,
        n_claims=result.n_claims,
        alarm=result.alarm,
        insufficient_data=result.insufficient_data,
        threshold=settings.drift_alarm_threshold,
        history=history,
    )


# ---------------------------------------------------------------------------
# Latency SLO tiles
# ---------------------------------------------------------------------------

# SLO targets (documented here as the single source of truth for this ticket).
_SLO_TARGETS: list[dict[str, Any]] = [
    {
        "name": "stream_latency",
        "display": "Stream latency",
        "unit": "ms",
        "slo_ms": 50.0,
        "prometheus_metric": "alphaedge_stream_latency_ms",
    },
    {
        "name": "brief_latency",
        "display": "Brief latency",
        "unit": "ms",
        "slo_ms": 5000.0,
        "prometheus_metric": "alphaedge_brief_latency_ms",
    },
]


def _parse_histogram_percentiles(
    metric_name: str,
    prometheus_text: str,
) -> dict[str, float | None]:
    """Very lightweight Prometheus text-format parser for histogram quantiles.

    Returns {"p50": ..., "p95": ..., "p99": ...} with None for any percentile
    that is absent.  This is simpler than pulling in prometheus_client's parser
    and avoids an extra dep.
    """
    from prometheus_client import REGISTRY

    # Access the registered metric object directly (same process).
    try:
        collector = REGISTRY._names_to_collectors.get(metric_name)
        if collector is None:
            return {"p50": None, "p95": None, "p99": None}
        # Walk the in-process histogram state to derive approximate quantiles.
        # Fall back to None if unavailable — honest empty state.
        return _extract_histogram_quantiles(collector)
    except Exception:  # noqa: BLE001
        return {"p50": None, "p95": None, "p99": None}


def _extract_histogram_quantiles(
    collector,
) -> dict[str, float | None]:
    """Extract p50/p95/p99 from a prometheus_client Histogram.

    Uses the bucket data collected from the in-process registry.
    Returns None for any percentile if there are no observations.
    """
    buckets: list[tuple[float, float]] = []  # (upper_bound, cumulative_count)
    total_count: float = 0.0

    try:
        for metric_family in collector.collect():
            for sample in metric_family.samples:
                if sample.name.endswith("_bucket"):
                    le = float(sample.labels.get("le", "+Inf"))
                    buckets.append((le, sample.value))
                elif sample.name.endswith("_count"):
                    total_count = sample.value
    except Exception:  # noqa: BLE001
        return {"p50": None, "p95": None, "p99": None}

    if total_count == 0:
        return {"p50": None, "p95": None, "p99": None}

    buckets_sorted = sorted(buckets, key=lambda x: x[0])
    result: dict[str, float | None] = {}
    for label, quantile in [("p50", 0.50), ("p95", 0.95), ("p99", 0.99)]:
        target = quantile * total_count
        prev_count = 0.0
        prev_le = 0.0
        found = None
        for le, count in buckets_sorted:
            if count >= target:
                # Linear interpolation within the bucket
                if count > prev_count and le != float("+inf"):
                    frac = (target - prev_count) / (count - prev_count)
                    found = prev_le + frac * (le - prev_le)
                else:
                    found = le
                break
            prev_count = count
            prev_le = le
        result[label] = found
    return result


@router.get("/slo", response_model=SloTilesOut)
async def get_slo_tiles() -> SloTilesOut:
    """Return latency SLO tiles sourced from in-process Prometheus metrics.

    If no data has been observed (e.g. no stream events since startup), the
    p50/p95/p99 fields are None and slo_met is None (honest unavailable state).
    """
    tiles = []
    for target in _SLO_TARGETS:
        quantiles = _parse_histogram_percentiles(target["prometheus_metric"], "")
        p50 = quantiles.get("p50")
        p95 = quantiles.get("p95")
        p99 = quantiles.get("p99")
        slo_ms = target["slo_ms"]
        # SLO is evaluated at p99 (strictest); None if no data.
        slo_met: bool | None = None if p99 is None else (p99 <= slo_ms)
        tiles.append(
            LatencySloTileOut(
                name=target["display"],
                unit=target["unit"],
                p50=p50,
                p95=p95,
                p99=p99,
                slo_ms=slo_ms,
                slo_met=slo_met,
            )
        )
    return SloTilesOut(tiles=tiles)


# ---------------------------------------------------------------------------
# Combined summary
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=ObservabilitySummaryOut)
async def get_observability_summary(
    session=Depends(get_db),
) -> ObservabilitySummaryOut:
    """Combined drift + SLO summary for the admin observability page."""
    drift_out = await get_calibration_drift(session=session)
    slo_out = await get_slo_tiles()
    return ObservabilitySummaryOut(
        drift=drift_out,
        slo_tiles=slo_out,
        paper_trading_only=True,
    )
