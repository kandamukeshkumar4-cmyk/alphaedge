from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
)
from app.forecasting import (
    BRIER_MIN_SAMPLE,
    CALIBRATION_BINS,
    CALIBRATION_MIN_SAMPLE,
)
from app.schemas.forecast import (
    CalibrationBin,
    CategoryEdge,
    DashboardMetrics,
    PracticeMetrics,
)


class _Row:
    __slots__ = ("forecast", "score", "market")

    def __init__(self, forecast: ForecastLog, score: ForecastScore | None, market: ExternalMarket):
        self.forecast = forecast
        self.score = score
        self.market = market


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


class ForecastDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(self, forecaster_id: UUID):
        result = await self.session.execute(
            select(ForecastLog, ForecastScore, ExternalMarket)
            .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
            .outerjoin(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
            .where(ForecastLog.forecaster_id == forecaster_id)
        )
        rows = [_Row(f, s, m) for f, s, m in result.all()]

        live_scored = [r for r in rows if r.forecast.mode == ForecastMode.LIVE and r.score]
        practice_scored = [
            r for r in rows if r.forecast.mode == ForecastMode.PRACTICE and r.score
        ]
        unresolved = [
            r
            for r in rows
            if r.forecast.mode == ForecastMode.LIVE
            and r.score is None
            and r.market.status != ExternalMarketStatus.RESOLVED
        ]

        live = self._live_metrics(live_scored, unresolved_count=len(unresolved))
        practice = self._practice_metrics(practice_scored)
        calibration = self._calibration(live_scored)
        categories = self._category_breakdown(live_scored)
        return live, practice, calibration, categories

    def _live_metrics(self, live_scored: list[_Row], unresolved_count: int) -> DashboardMetrics:
        independent = [r for r in live_scored if r.forecast.is_independent]
        anchored = [r for r in live_scored if not r.forecast.is_independent]

        user_briers = [float(r.score.user_brier) for r in live_scored]
        market_briers = [
            float(r.score.market_brier) for r in live_scored if r.score.market_brier is not None
        ]
        # Edge-over-market only counts independent forecasts (anchored ones carry no signal).
        deltas = [
            float(r.score.brier_delta)
            for r in independent
            if r.score.brier_delta is not None
        ]
        pnl_total = round(sum(float(r.score.synthetic_pnl) for r in live_scored), 4)

        resolved_count = len(live_scored)
        return DashboardMetrics(
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
            independent_count=len(independent),
            anchored_count=len(anchored),
            mean_user_brier=_mean(user_briers),
            mean_market_brier=_mean(market_briers),
            mean_brier_delta=_mean(deltas),
            synthetic_pnl_total=pnl_total,
            brier_provisional=resolved_count < BRIER_MIN_SAMPLE,
            calibration_provisional=len(independent) < CALIBRATION_MIN_SAMPLE,
        )

    def _practice_metrics(self, practice_scored: list[_Row]) -> PracticeMetrics:
        independent = [r for r in practice_scored if r.forecast.is_independent]
        return PracticeMetrics(
            resolved_count=len(practice_scored),
            mean_user_brier=_mean([float(r.score.user_brier) for r in practice_scored]),
            mean_brier_delta=_mean(
                [
                    float(r.score.brier_delta)
                    for r in independent
                    if r.score.brier_delta is not None
                ]
            ),
        )

    def _calibration(self, live_scored: list[_Row]) -> list[CalibrationBin]:
        independent = [r for r in live_scored if r.forecast.is_independent]
        bins: list[CalibrationBin] = []
        width = 1.0 / CALIBRATION_BINS
        for i in range(CALIBRATION_BINS):
            lower = i * width
            upper = (i + 1) * width
            in_bin = [
                r
                for r in independent
                if lower <= float(r.forecast.user_probability) < upper
                or (i == CALIBRATION_BINS - 1 and float(r.forecast.user_probability) == 1.0)
            ]
            predicted = [float(r.forecast.user_probability) for r in in_bin]
            observed = [float(r.score.actual_outcome) for r in in_bin]
            bins.append(
                CalibrationBin(
                    lower=round(lower, 4),
                    upper=round(upper, 4),
                    count=len(in_bin),
                    mean_predicted=_mean(predicted),
                    observed_frequency=_mean(observed),
                )
            )
        return bins

    def _category_breakdown(self, live_scored: list[_Row]) -> list[CategoryEdge]:
        independent = [r for r in live_scored if r.forecast.is_independent]
        by_category: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        for r in independent:
            cat = r.market.category or "Uncategorized"
            counts[cat] = counts.get(cat, 0) + 1
            if r.score.brier_delta is not None:
                by_category.setdefault(cat, []).append(float(r.score.brier_delta))
        return [
            CategoryEdge(
                category=cat,
                count=counts[cat],
                mean_brier_delta=_mean(by_category.get(cat, [])),
            )
            for cat in sorted(counts)
        ]
