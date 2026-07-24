"""Read-only orchestration for the Phase 1 factor and validator graph."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.factors import FACTOR_FUNCTIONS
from app.alpha.validator import validate_all_factors
from app.db.models import ExternalMarket, ForecastLog


class AlphaService:
    """Return research scores and independent validation; never constructs orders."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def factors_for_market(self, market: str) -> dict[str, Any]:
        external_market = await self._external_market(market)
        validations = {item["name"]: item for item in await validate_all_factors(self._session)}
        forecast = await self._latest_forecast(external_market.id)
        factors, as_of = _current_factors(forecast)
        results = [_combine(result, validations[result["name"]]) for result in factors]
        rejected = [
            {"name": item["name"], "reason": item["reason"]}
            for item in results
            if not item["valid"]
        ]
        return {
            "market": external_market.external_id,
            "as_of": _utc_iso(as_of),
            "factors": results,
            "rejected_factors": rejected,
            "paper_trading_only": True,
        }

    async def report(self) -> dict[str, Any]:
        factors = await validate_all_factors(self._session)
        rejected = [
            {"name": item["name"], "reason": item["reason"]}
            for item in factors
            if not item["valid"]
        ]
        return {
            "factors": factors,
            "valid_factor_count": sum(bool(item["valid"]) for item in factors),
            "rejected_factors": rejected,
            "paper_trading_only": True,
        }

    async def _external_market(self, market: str) -> ExternalMarket:
        result = await self._session.execute(
            select(ExternalMarket).where(ExternalMarket.external_id == market)
        )
        external_market = result.scalar_one_or_none()
        if external_market is None:
            raise LookupError("market_not_found")
        return external_market

    async def _latest_forecast(self, external_market_id: object) -> ForecastLog | None:
        result = await self._session.execute(
            select(ForecastLog)
            .where(ForecastLog.external_market_id == external_market_id)
            .order_by(ForecastLog.locked_at.desc(), ForecastLog.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _current_factors(forecast: ForecastLog | None) -> tuple[list[dict[str, Any]], datetime | None]:
    if forecast is None:
        return [_missing(name, "missing_locked_forecast") for name in FACTOR_FUNCTIONS], None
    metadata = forecast.snapshot_metadata or {}
    captured = metadata.get("alpha_features")
    features = dict(captured) if isinstance(captured, dict) else {}
    model = _probability(forecast.user_probability)
    market = _probability(forecast.market_implied_probability)
    features["model_probability"] = model
    features["market_implied_probability"] = market
    features["edge"] = None if model is None or market is None else model - market
    seconds = forecast.time_to_resolution_seconds
    features["hours_to_lock"] = None if seconds is None else float(seconds) / 3600.0
    return [function(features) for function in FACTOR_FUNCTIONS.values()], forecast.locked_at


def _combine(current: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    available = bool(current["provenance"]["available"])
    valid = available and bool(validation["valid"])
    reason = None
    if not available:
        reason = current["provenance"]["reason"]
    elif not valid:
        reason = validation["reason"]
    return {
        "name": current["name"],
        "score": current["score"],
        "valid": valid,
        "t_stat": validation.get("t_stat"),
        "reason": reason,
        "provenance": current["provenance"],
    }


def _missing(name: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "score": 0.0,
        "provenance": {"available": False, "reason": reason},
    }


def _probability(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    return probability if 0.0 <= probability <= 1.0 else None


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()
