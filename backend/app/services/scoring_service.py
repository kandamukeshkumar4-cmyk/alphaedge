from __future__ import annotations

from datetime import timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
)
from app.events.bus import DomainEventBus
from app.forecasting import scoring


class ScoringService:
    """Scores locked forecasts after their market resolves.

    Leakage gate: a LIVE forecast is only scored if it was locked strictly before
    the market's resolution timestamp. A forecast locked at/after resolution
    cannot count toward the real track record (it would be hindsight)."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def score_market(self, external_market: ExternalMarket) -> int:
        if (
            external_market.status != ExternalMarketStatus.RESOLVED
            or external_market.winning_outcome is None
        ):
            raise ValueError("Cannot score an unresolved market")

        outcome = int(external_market.winning_outcome)
        resolved_at = external_market.resolved_at
        if resolved_at is not None and resolved_at.tzinfo is None:
            resolved_at = resolved_at.replace(tzinfo=timezone.utc)

        result = await self.session.execute(
            select(ForecastLog).where(
                ForecastLog.external_market_id == external_market.id
            )
        )
        forecasts = list(result.scalars().all())

        existing_scores = await self.session.execute(
            select(ForecastScore.forecast_id).where(
                ForecastScore.forecast_id.in_([f.id for f in forecasts])
            )
        )
        already_scored = {row[0] for row in existing_scores.all()}

        scored = 0
        for forecast in forecasts:
            if forecast.id in already_scored:
                continue

            # Leakage gate for LIVE forecasts: must be locked before resolution.
            if forecast.mode == ForecastMode.LIVE and resolved_at is not None:
                locked_at = forecast.locked_at
                if locked_at is not None and locked_at.tzinfo is None:
                    locked_at = locked_at.replace(tzinfo=timezone.utc)
                if locked_at is not None and locked_at >= resolved_at:
                    await self.events.emit(
                        "forecast_score_skipped_leakage",
                        {"forecast_id": str(forecast.id)},
                    )
                    continue

            implied = (
                float(forecast.market_implied_probability)
                if forecast.market_implied_probability is not None
                else None
            )
            res = scoring.score_forecast(
                user_probability=float(forecast.user_probability),
                implied_probability=implied,
                outcome=outcome,
            )
            self.session.add(
                ForecastScore(
                    forecast_id=forecast.id,
                    actual_outcome=res.actual_outcome,
                    user_brier=_dec6(res.user_brier),
                    market_brier=_dec6(res.market_brier) if res.market_brier is not None else None,
                    brier_delta=_dec6(res.brier_delta) if res.brier_delta is not None else None,
                    synthetic_pnl=Decimal(str(round(res.synthetic_pnl, 4))),
                )
            )
            scored += 1

        if scored:
            await self.session.flush()
            await self.events.emit(
                "forecasts_scored",
                {"external_market_id": str(external_market.id), "count": scored},
            )
        return scored


def _dec6(value: float) -> Decimal:
    return Decimal(str(round(value, 6)))
