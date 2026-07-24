"""Independent, read-only validator for Phase 1 alpha factors.

The maker functions in :mod:`app.alpha.factors` never validate themselves.
This module evaluates only immutable lock-time inputs on the existing scored
forecast population, then compares their out-of-sample Brier performance with
an explicitly captured closing line.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import math
import random
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.factors import FACTOR_FUNCTIONS
from app.backtesting.clv import ForecastComparison, evaluate_forecasts_against_closing
from app.db.models import ForecastLog
from app.ml.forecast_ab_dataset import load_forecast_score_rows


BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20_260_724
MIN_OBSERVATIONS = 20
MIN_OOS_OBSERVATIONS = 8
IS_FRACTION = 0.60
MAX_OOS_DEGRADATION = 0.30
MIN_T_STAT = 2.0
FACTOR_AMPLITUDE = 0.10


@dataclass(frozen=True)
class FactorObservation:
    factor: str
    score: float
    entry_probability: float
    closing_probability: float
    outcome: int
    locked_at: datetime
    forecast_id: str
    correlation_cluster: str


async def load_factor_observations(
    session: AsyncSession, factor: str
) -> tuple[list[FactorObservation], dict[str, int]]:
    """Load one factor's immutable, scored observations without backfilling.

    The source relation retains the accuracy gate's resolved/LIVE population,
    timestamp ordering, and correlation clusters. Only the matching locked
    forecast metadata is read to recover the factor's own captured inputs.
    """
    if factor not in FACTOR_FUNCTIONS:
        raise ValueError(f"unknown factor: {factor}")

    population = await load_forecast_score_rows(session)
    ids = [UUID(row["forecast_id"]) for row in population]
    if not ids:
        return [], {"missing_factor_provenance": 0, "missing_closing_line": 0}

    records = await session.execute(
        select(
            ForecastLog.id,
            ForecastLog.user_probability,
            ForecastLog.market_implied_probability,
            ForecastLog.time_to_resolution_seconds,
            ForecastLog.snapshot_metadata,
        ).where(ForecastLog.id.in_(ids))
    )
    locked = {str(row.id): row for row in records.all()}
    observations: list[FactorObservation] = []
    missing = {"missing_factor_provenance": 0, "missing_closing_line": 0}
    for row in population:
        forecast = locked.get(row["forecast_id"])
        if forecast is None:
            missing["missing_factor_provenance"] += 1
            continue
        features = _lock_features(forecast)
        result = FACTOR_FUNCTIONS[factor](features)
        if not result["provenance"]["available"]:
            missing["missing_factor_provenance"] += 1
            continue
        entry = _probability(features.get("market_implied_probability"))
        closing = _probability((forecast.snapshot_metadata or {}).get("closing_implied_probability"))
        if entry is None:
            missing["missing_factor_provenance"] += 1
            continue
        if closing is None:
            missing["missing_closing_line"] += 1
            continue
        score = float(result["score"])
        if not math.isfinite(score):
            missing["missing_factor_provenance"] += 1
            continue
        cluster = str(row.get("correlation_cluster") or f"uncorrelated:{row['forecast_id']}")
        observations.append(
            FactorObservation(
                factor=factor,
                score=score,
                entry_probability=entry,
                closing_probability=closing,
                outcome=int(row["actual_outcome"]),
                locked_at=row["locked_at"],
                forecast_id=row["forecast_id"],
                correlation_cluster=cluster,
            )
        )
    return observations, missing


async def validate_factor(session: AsyncSession, factor: str) -> dict[str, Any]:
    observations, missing = await load_factor_observations(session, factor)
    return validate_factor_observations(factor, observations, missing=missing)


async def validate_all_factors(session: AsyncSession) -> list[dict[str, Any]]:
    return [await validate_factor(session, name) for name in FACTOR_FUNCTIONS]


def validate_factor_observations(
    factor: str,
    observations: Iterable[FactorObservation],
    *,
    missing: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Apply the Phase 1 chronological OOS, bootstrap, and HAC kill gates."""
    ordered = sorted(observations, key=lambda item: (item.locked_at, item.forecast_id))
    missing = missing or {}
    base = _base_result(factor, len(ordered), missing)
    if not ordered:
        reason = (
            "missing_closing_line"
            if missing.get("missing_closing_line", 0)
            else "insufficient_factor_provenance"
        )
        return _reject(base, reason)
    if len(ordered) < MIN_OBSERVATIONS:
        return _reject(base, "insufficient_oos_rows")
    clusters = {item.correlation_cluster for item in ordered}
    if len(clusters) < 2:
        return _reject(base, "insufficient_correlation_clusters")

    is_count = math.floor(len(ordered) * IS_FRACTION)
    is_rows, oos_rows = ordered[:is_count], ordered[is_count:]
    if len(oos_rows) < MIN_OOS_OBSERVATIONS:
        return _reject(base, "insufficient_oos_rows")
    is_evaluation = _evaluate(is_rows)
    oos_evaluation = _evaluate(oos_rows)
    deltas = _brier_deltas(oos_rows)
    bootstrap_lower = _bootstrap_lower(deltas, oos_rows)
    t_stat = _newey_west_t_stat(deltas)
    degradation = _degradation(is_evaluation.model_brier, oos_evaluation.model_brier)
    base.update(
        {
            "is_brier": round(is_evaluation.model_brier, 6),
            "oos_brier": round(oos_evaluation.model_brier, 6),
            "closing_brier": round(oos_evaluation.closing_brier, 6),
            "brier_delta_vs_closing": round(oos_evaluation.brier_delta_vs_closing, 6),
            "bootstrap_lower": round(bootstrap_lower, 6),
            "t_stat": round(t_stat, 6),
            "oos_degradation": round(degradation, 6) if math.isfinite(degradation) else None,
            "oos_count": len(oos_rows),
            "correlation_clusters": len(clusters),
        }
    )
    if oos_evaluation.model_brier >= oos_evaluation.closing_brier:
        return _reject(base, "oos_does_not_beat_closing")
    if bootstrap_lower <= 0.0:
        return _reject(base, "bootstrap_ci_not_positive")
    if t_stat < MIN_T_STAT:
        return _reject(base, "t_stat_below_threshold")
    if degradation > MAX_OOS_DEGRADATION:
        return _reject(base, "oos_degradation_exceeds_limit")
    base.update({"valid": True, "reason": None})
    return base


def _lock_features(forecast: Any) -> dict[str, Any]:
    metadata = forecast.snapshot_metadata or {}
    alpha_features = metadata.get("alpha_features")
    features = dict(alpha_features) if isinstance(alpha_features, dict) else {}
    model = _probability(forecast.user_probability)
    market = _probability(forecast.market_implied_probability)
    features["model_probability"] = model
    features["market_implied_probability"] = market
    features["edge"] = None if model is None or market is None else model - market
    seconds = forecast.time_to_resolution_seconds
    features["hours_to_lock"] = None if seconds is None else float(seconds) / 3600.0
    return features


def _evaluate(rows: list[FactorObservation]):
    return evaluate_forecasts_against_closing(
        [
            ForecastComparison(
                predicted_prob=_prediction(item.entry_probability, item.score),
                closing_implied=item.closing_probability,
                outcome=item.outcome,
            )
            for item in rows
        ]
    )


def _brier_deltas(rows: list[FactorObservation]) -> list[float]:
    return [
        (item.closing_probability - item.outcome) ** 2
        - (_prediction(item.entry_probability, item.score) - item.outcome) ** 2
        for item in rows
    ]


def _bootstrap_lower(deltas: list[float], rows: list[FactorObservation]) -> float:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item, delta in zip(rows, deltas):
        grouped[item.correlation_cluster].append(delta)
    cluster_means = {name: math.fsum(values) / len(values) for name, values in grouped.items()}
    names = sorted(cluster_means)
    generator = random.Random(BOOTSTRAP_SEED)
    samples = sorted(
        math.fsum(cluster_means[generator.choice(names)] for _ in names) / len(names)
        for _ in range(BOOTSTRAP_SAMPLES)
    )
    return samples[math.ceil(0.05 * BOOTSTRAP_SAMPLES) - 1]


def _newey_west_t_stat(deltas: list[float]) -> float:
    count = len(deltas)
    mean = math.fsum(deltas) / count
    lag = math.floor(count ** (1 / 3))
    centered = [item - mean for item in deltas]
    variance = math.fsum(item * item for item in centered) / count
    for offset in range(1, lag + 1):
        covariance = math.fsum(
            centered[index] * centered[index - offset] for index in range(offset, count)
        ) / count
        variance += 2.0 * (1.0 - offset / (lag + 1)) * covariance
    if variance <= 1e-12:
        return 999.0 if mean > 0.0 else -999.0 if mean < 0.0 else 0.0
    return mean / math.sqrt(variance / count)


def _prediction(entry: float, score: float) -> float:
    return min(1.0, max(0.0, entry + FACTOR_AMPLITUDE * score))


def _degradation(is_brier: float, oos_brier: float) -> float:
    if is_brier <= 1e-12:
        return 0.0 if oos_brier <= is_brier else float("inf")
    return (oos_brier - is_brier) / is_brier


def _base_result(factor: str, count: int, missing: dict[str, int]) -> dict[str, Any]:
    return {
        "name": factor,
        "valid": False,
        "reason": None,
        "count": count,
        "missing_factor_provenance": missing.get("missing_factor_provenance", 0),
        "missing_closing_line": missing.get("missing_closing_line", 0),
        "t_stat": None,
    }


def _reject(result: dict[str, Any], reason: str) -> dict[str, Any]:
    result["reason"] = reason
    return result


def _probability(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        return None
    return probability
