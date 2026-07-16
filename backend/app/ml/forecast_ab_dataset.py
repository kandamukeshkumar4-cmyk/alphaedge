"""Forecast-score population and leakage-safe folds for the V40 A/B readout.

This module deliberately does *not* consume the legacy odds-snapshot matrix.
The only evaluation population is a scored, LIVE ``ForecastLog`` joined to its
``ExternalMarket``.  Feature values are restricted to fields recorded at lock
time; resolution fields are labels/split boundaries only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalMarket, ExternalMarketStatus, ForecastLog, ForecastMode, ForecastScore
from app.ml.concentration import build_report, correlation_cluster
from app.workers.forecast_autolock import AUTOLOCK_FORECASTER_ID

# These are the two values present for every valid autolock at prediction time.
# They are intentionally not enriched with current market/catalog data.
FORECAST_AB_FEATURE_COLUMNS = (
    "market_implied_probability",
    "time_to_resolution_hours",
)
DEFAULT_TRAIN_WINDOW_SIZE = 4
DEFAULT_EVAL_WINDOW_SIZE = 2
# A one-row resolution-time embargo is explicit rather than silently inheriting
# the old trainer's zero default. It removes the newest eligible labels before
# each evaluation boundary.
DEFAULT_EMBARGO_RESOLVED_ROWS = 1


@dataclass(frozen=True)
class ForecastAbFold:
    train_rows: list[dict[str, Any]]
    eval_rows: list[dict[str, Any]]
    eval_min_locked_at: datetime
    embargoed_forecast_ids: list[str]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def load_forecast_score_rows(session: AsyncSession) -> list[dict[str, Any]]:
    """Return the V40 evaluation relation, without paper-order fallback.

    ``ForecastScore.scored_at`` is deliberately absent. It is a grading time,
    not information available when a forecast was locked or an outcome resolved.
    """
    result = await session.execute(
        select(ForecastScore, ForecastLog, ExternalMarket)
        .join(ForecastLog, ForecastLog.id == ForecastScore.forecast_id)
        .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
        .where(
            ForecastLog.mode == ForecastMode.LIVE,
            ExternalMarket.status == ExternalMarketStatus.RESOLVED,
            ExternalMarket.winning_outcome.is_not(None),
        )
        .order_by(ForecastLog.locked_at.asc(), ForecastLog.id.asc())
    )
    rows: list[dict[str, Any]] = []
    for score, forecast, market in result.all():
        metadata = forecast.snapshot_metadata or {}
        rows.append(
            {
                "forecast_id": str(forecast.id),
                "forecast_score_id": str(score.id),
                "external_market_id": str(market.id),
                "external_id": market.external_id,
                "category": market.category,
                "platform": getattr(market.platform, "value", market.platform),
                "forecaster_id": str(forecast.forecaster_id),
                "is_model_autolock": forecast.forecaster_id == AUTOLOCK_FORECASTER_ID
                or metadata.get("lock_origin") == "model_autolock",
                "market_implied_probability": _number(forecast.market_implied_probability),
                "time_to_resolution_hours": _horizon_hours(forecast.time_to_resolution_seconds),
                "locked_at": _utc(forecast.locked_at),
                "close_at": _utc(market.close_at),
                "resolved_at": _utc(market.resolved_at),
                "actual_outcome": int(score.actual_outcome),
                "correlation_cluster": correlation_cluster(market.external_id),
                "model_provisional": bool(metadata.get("model_provisional")),
                "clv_gate_passed": bool(metadata.get("clv_gate_passed")),
            }
        )
    return rows


def population_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Describe the scored population and make invalid provenance visible.

    Invalid timestamps/features are a refusal condition.  They are never silently
    filtered out to make the population look cleaner or more independent.
    """
    materialized = list(rows)
    invalid = Counter()
    for row in materialized:
        locked_at = row.get("locked_at")
        close_at = row.get("close_at")
        resolved_at = row.get("resolved_at")
        if locked_at is None:
            invalid["missing_locked_at"] += 1
        if close_at is None:
            invalid["missing_close_at"] += 1
        if resolved_at is None:
            invalid["missing_resolved_at"] += 1
        if locked_at is not None and close_at is not None and locked_at >= close_at:
            invalid["post_close_lock"] += 1
        if locked_at is not None and resolved_at is not None and locked_at >= resolved_at:
            invalid["post_resolution_lock"] += 1
        for feature in FORECAST_AB_FEATURE_COLUMNS:
            value = row.get(feature)
            if value is None or not pd.notna(value):
                invalid[f"missing_feature:{feature}"] += 1

    report = build_report(materialized, mode="forecast_scores")
    autolock_count = sum(bool(row.get("is_model_autolock")) for row in materialized)
    report.update(
        {
            "dataset_source": "forecast_scores",
            "forecast_scored_count": len(materialized),
            "model_autolock_count": autolock_count,
            "human_or_other_forecast_count": len(materialized) - autolock_count,
            "feature_columns": list(FORECAST_AB_FEATURE_COLUMNS),
            "invalid_row_reasons": dict(sorted(invalid.items())),
            "valid_for_ab": not invalid,
        }
    )
    return report


def build_v40_folds(
    rows: Iterable[dict[str, Any]],
    *,
    train_window_size: int = DEFAULT_TRAIN_WINDOW_SIZE,
    eval_window_size: int = DEFAULT_EVAL_WINDOW_SIZE,
    embargo_resolved_rows: int = DEFAULT_EMBARGO_RESOLVED_ROWS,
) -> list[ForecastAbFold]:
    """Build V40 splits ordered by lock time, trained only on known outcomes.

    For each fold, ``T_eval_min`` is the first evaluation lock. Training labels
    must have resolved before that boundary. The newest eligible labels are
    embargoed before selecting the fixed-size training window.
    """
    materialized = list(rows)
    summary = population_summary(materialized)
    if not summary["valid_for_ab"]:
        raise ValueError("forecast_score_population_invalid")

    ordered = sorted(materialized, key=lambda row: (row["locked_at"], row["forecast_id"]))
    folds: list[ForecastAbFold] = []
    # Start after the nominal warm-up, but actual eligibility remains governed by
    # resolved_at. Skipping a fold with too few available outcomes is honest.
    start = train_window_size + embargo_resolved_rows
    for eval_start in range(start, len(ordered), eval_window_size):
        eval_rows = ordered[eval_start : eval_start + eval_window_size]
        if not eval_rows:
            continue
        eval_min = eval_rows[0]["locked_at"]
        eligible = [row for row in ordered[:eval_start] if row["resolved_at"] < eval_min]
        eligible.sort(key=lambda row: (row["resolved_at"], row["forecast_id"]))
        embargoed = eligible[-embargo_resolved_rows:] if embargo_resolved_rows else []
        train_candidates = eligible[:-embargo_resolved_rows] if embargo_resolved_rows else eligible
        train_rows = train_candidates[-train_window_size:]
        if len(train_rows) < train_window_size:
            continue
        if any(row["resolved_at"] >= eval_min for row in train_rows):
            raise AssertionError("V40 split leakage: train resolved after eval boundary")
        if any(row["locked_at"] < eval_min for row in eval_rows):
            raise AssertionError("V40 split leakage: eval locked before eval boundary")
        folds.append(
            ForecastAbFold(
                train_rows=train_rows,
                eval_rows=eval_rows,
                eval_min_locked_at=eval_min,
                embargoed_forecast_ids=[row["forecast_id"] for row in embargoed],
            )
        )
    return folds


def _number(value: object | None) -> float | None:
    return None if value is None else float(value)


def _horizon_hours(value: object | None) -> float | None:
    return None if value is None else float(value) / 3600.0
