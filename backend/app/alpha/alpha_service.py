"""Read-only orchestration for the Phase 1 factor and validator graph."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.factors import FACTOR_FUNCTIONS
from app.alpha.validator import validate_all_factors
from app.db.models import AlphaFactorSnapshot, ExternalMarket, ForecastLog


class AlphaService:
    """Return research scores and independent validation; never constructs orders."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def factors_for_market(self, market: str) -> dict[str, Any]:
        external_market = await self._external_market(market)
        validations = {item["name"]: item for item in await validate_all_factors(self._session)}
        forecast = await self._latest_forecast(external_market.id)
        snapshot = (
            await self._factor_snapshot(forecast.id) if forecast is not None else None
        )
        factors, as_of = _current_factors(forecast, snapshot)
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

    async def _factor_snapshot(
        self, forecast_id: object
    ) -> AlphaFactorSnapshot | None:
        return await self._session.scalar(
            select(AlphaFactorSnapshot).where(
                AlphaFactorSnapshot.forecast_id == forecast_id
            )
        )


def _current_factors(
    forecast: ForecastLog | None,
    snapshot: AlphaFactorSnapshot | None,
) -> tuple[list[dict[str, Any]], datetime | None]:
    if forecast is None:
        return [_missing(name, "missing_locked_forecast") for name in FACTOR_FUNCTIONS], None
    if snapshot is None:
        return [
            _missing(name, "missing_factor_snapshot") for name in FACTOR_FUNCTIONS
        ], forecast.locked_at
    factor_values = (
        snapshot.factor_values if isinstance(snapshot.factor_values, dict) else {}
    )
    capture_provenance = (
        snapshot.factor_provenance
        if isinstance(snapshot.factor_provenance, dict)
        else {}
    )
    results: list[dict[str, Any]] = []
    for name in FACTOR_FUNCTIONS:
        provenance = capture_provenance.get(name)
        if not isinstance(provenance, dict) or not provenance.get("available"):
            reason = (
                provenance.get("reason")
                if isinstance(provenance, dict)
                else "missing_factor_provenance"
            )
            results.append(_missing(name, str(reason)))
            continue
        score = factor_values.get(name)
        if isinstance(score, bool):
            results.append(_missing(name, "missing_captured_factor_value"))
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            results.append(_missing(name, "missing_captured_factor_value"))
            continue
        if not math.isfinite(score):
            results.append(_missing(name, "missing_captured_factor_value"))
            continue
        results.append(
            {
                "name": name,
                "score": score,
                "provenance": {
                    "available": True,
                    "fields": list(provenance.get("fields", [])),
                    "capture": provenance,
                },
            }
        )
    return results, snapshot.observed_at


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


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()
