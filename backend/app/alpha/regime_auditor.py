"""Independent regime audit for validated alpha factors.

The validator establishes chronological out-of-sample evidence.  This node
then checks that evidence across only observed lock-time regimes; it never
invents missing volume, time-to-close, or category provenance.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.validator import FactorObservation, load_factor_observations
from app.db.models import ExternalMarket, ForecastLog


MIN_REGIME_ROWS = 4
MIN_PREDICTIVE_REGIMES = 2


@dataclass(frozen=True)
class RegimeObservation:
    """A scored factor observation with its captured regime provenance."""

    observation: FactorObservation
    volume: float | None
    hours_to_close: float | None
    category: str | None


async def load_regime_observations(
    session: AsyncSession, factor: str
) -> tuple[list[RegimeObservation], dict[str, int]]:
    """Reuse the validator's resolved population and add observed regime fields."""
    observations, missing = await load_factor_observations(session, factor)
    if not observations:
        return [], {**missing, "missing_regime_provenance": 0}
    ids = [item.forecast_id for item in observations]
    rows = await session.execute(
        select(ForecastLog.id, ForecastLog.time_to_resolution_seconds, ForecastLog.snapshot_metadata,
               ExternalMarket.category)
        .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
        .where(ForecastLog.id.in_(ids))
    )
    captured = {str(row.id): row for row in rows.all()}
    result: list[RegimeObservation] = []
    missing_regime = 0
    for observation in observations:
        row = captured.get(observation.forecast_id)
        if row is None:
            missing_regime += 1
            continue
        metadata = row.snapshot_metadata or {}
        features = metadata.get("alpha_features")
        volume = _number(metadata.get("volume"))
        if volume is None and isinstance(features, dict):
            volume = _number(features.get("volume"))
        hours = None
        if row.time_to_resolution_seconds is not None:
            hours = float(row.time_to_resolution_seconds) / 3600.0
        category = row.category.strip() if isinstance(row.category, str) and row.category.strip() else None
        if volume is None or volume < 0.0 or hours is None or hours < 0.0 or category is None:
            missing_regime += 1
            continue
        result.append(RegimeObservation(observation, volume, hours, category))
    return result, {**missing, "missing_regime_provenance": missing_regime}


def audit_factor_regimes(
    factor: str,
    observations: Iterable[RegimeObservation],
    *,
    validator_result: dict[str, Any],
) -> dict[str, Any]:
    """Kill a factor whose positive predictive statistic occurs in one regime."""
    rows = list(observations)
    result: dict[str, Any] = {
        "name": factor,
        "valid": False,
        "reason": None,
        "regimes": [],
        "predictive_regime_count": 0,
        "paper_trading_only": True,
    }
    if not validator_result.get("valid"):
        result["reason"] = "validator_rejected"
        return result
    grouped: dict[str, list[RegimeObservation]] = defaultdict(list)
    for item in rows:
        grouped[_regime_key(item)].append(item)
    if not grouped:
        result["reason"] = "insufficient_regime_provenance"
        return result
    summaries = []
    for key in sorted(grouped):
        group = grouped[key]
        delta = math.fsum(_predictive_delta(item.observation) for item in group) / len(group)
        summaries.append({
            "regime": key,
            "count": len(group),
            "predictive_stat": round(delta, 6),
            "predictive": len(group) >= MIN_REGIME_ROWS and delta > 0.0,
        })
    result["regimes"] = summaries
    predictive_count = sum(bool(item["predictive"]) for item in summaries)
    result["predictive_regime_count"] = predictive_count
    if predictive_count < MIN_PREDICTIVE_REGIMES:
        result["reason"] = "only_one_predictive_regime"
        return result
    result["valid"] = True
    return result


def _predictive_delta(item: FactorObservation) -> float:
    prediction = min(1.0, max(0.0, item.entry_probability + 0.10 * item.score))
    return (item.closing_probability - item.outcome) ** 2 - (prediction - item.outcome) ** 2


def _regime_key(item: RegimeObservation) -> str:
    return f"{_volume_tier(item.volume)}|{_hours_bucket(item.hours_to_close)}|{item.category}"


def _volume_tier(volume: float) -> str:
    if volume < 1_000:
        return "low_volume"
    if volume < 10_000:
        return "mid_volume"
    return "high_volume"


def _hours_bucket(hours: float) -> str:
    if hours <= 24.0:
        return "near_close"
    if hours <= 168.0:
        return "mid_horizon"
    return "far_horizon"


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
