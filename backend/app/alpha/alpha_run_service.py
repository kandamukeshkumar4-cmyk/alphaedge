"""Daily orchestration and persistence for the multi-factor alpha graph."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.portfolio_constructor import construct_research_weights
from app.alpha.regime_auditor import audit_factor_regimes, load_regime_observations
from app.alpha.risk_decomposer import decompose_oos_returns
from app.alpha.validator import validate_all_factors
from app.db.models import AlphaRun


class AlphaRunService:
    """Run the sequential research tail without an execution-path dependency."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run_daily(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = _utc(now or datetime.now(UTC))
        existing = await self._session.scalar(select(AlphaRun).where(AlphaRun.run_date == now.date()))
        if existing is not None:
            return _serialize(existing, reused=True)
        validations = await validate_all_factors(self._session)
        rejections = [
            {"node": "validator", "factor": item["name"], "reason": item["reason"]}
            for item in validations
            if not item.get("valid")
        ]
        regimes: list[dict[str, Any]] = []
        factor_returns: dict[str, dict[str, float]] = {}
        for validation in validations:
            if not validation.get("valid"):
                continue
            factor = str(validation["name"])
            observations, _missing = await load_regime_observations(self._session, factor)
            audit = audit_factor_regimes(factor, observations, validator_result=validation)
            regimes.append(audit)
            if not audit["valid"]:
                rejections.append({"node": "regime_auditor", "factor": factor, "reason": audit["reason"]})
                continue
            factor_returns[factor] = _oos_research_returns(observations)
        constructor = construct_research_weights(factor_returns)
        if not constructor["constructed"]:
            rejections.append({"node": "portfolio_constructor", "reason": constructor["reason"]})
            decomposition = {
                "status": "no_signal",
                "reason": "portfolio_not_constructed",
                "residual_alpha": None,
                "residual_alpha_t_stat": None,
                "threshold": 2.5,
                "oos_count": 0,
                "factor_betas": {},
                "paper_trading_only": True,
            }
        else:
            decomposition = decompose_oos_returns(constructor["combined_returns"], factor_returns)
            if decomposition["status"] != "genuine_edge":
                rejections.append({"node": "risk_decomposer", "reason": decomposition["reason"]})
        status = str(decomposition["status"])
        result = {
            "validations": validations,
            "regimes": regimes,
            "constructor": constructor,
            "decomposition": decomposition,
            "signal": {
                "label": "genuine edge" if status == "genuine_edge" else "no signal (evidence)",
                "status": status,
                "weights": constructor["weights"],
                "residual_alpha_t_stat": decomposition["residual_alpha_t_stat"],
                "threshold": decomposition["threshold"],
            },
        }
        run = AlphaRun(
            run_date=now.date(),
            status=status,
            result=result,
            rejection_reasons=rejections,
            paper_trading_only=True,
        )
        self._session.add(run)
        await self._session.flush()
        return _serialize(run, reused=False)

    async def runs(self, *, limit: int = 30) -> dict[str, Any]:
        rows = await self._session.scalars(
            select(AlphaRun).order_by(AlphaRun.run_date.desc()).limit(max(1, min(limit, 100)))
        )
        items = [_serialize(row, reused=False) for row in rows]
        return {"latest": items[0] if items else None, "runs": items, "paper_trading_only": True}

    async def latest_signal(self) -> dict[str, Any]:
        row = await self._session.scalar(select(AlphaRun).order_by(AlphaRun.run_date.desc()).limit(1))
        if row is None:
            return {"signal": None, "reason": "no_alpha_runs", "paper_trading_only": True}
        return {
            "run_date": row.run_date.isoformat(),
            "signal": (row.result or {}).get("signal"),
            "rejection_reasons": row.rejection_reasons or [],
            "paper_trading_only": True,
        }


async def run_alpha_model_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ/in-process shared daily entrypoint; commits only research evidence."""
    from app.db.session import AsyncSessionLocal

    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    async with session_factory() as session:
        result = await AlphaRunService(session).run_daily(now=ctx.get("now"))
        await session.commit()
    return result


def _oos_research_returns(observations: list[Any]) -> dict[str, float]:
    ordered = sorted(
        (item.observation for item in observations), key=lambda item: (item.locked_at, item.forecast_id)
    )
    start = math.floor(len(ordered) * 0.60)
    return {
        item.forecast_id: item.score * (item.outcome - item.entry_probability)
        for item in ordered[start:]
    }


def _serialize(run: AlphaRun, *, reused: bool) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "run_date": run.run_date.isoformat(),
        "status": run.status,
        "result": run.result,
        "rejection_reasons": run.rejection_reasons,
        "paper_trading_only": True,
        "reused": reused,
    }


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
