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
    BrierTrendPoint,
    CalibrationBin,
    CategoryEdge,
    DashboardMetrics,
    PlatformEdge,
    PracticeMetrics,
    TimeBucketEdge,
)

TIME_BUCKETS = ("7d+", "1-7d", "6-24h", "1-6h", "<1h", "unknown")


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
        platforms = self._platform_breakdown(live_scored)
        time_buckets = self._time_breakdown(live_scored)
        brier_trend = self._brier_trend(live_scored)
        return live, practice, calibration, categories, platforms, time_buckets, brier_trend

    def _live_metrics(self, live_scored: list[_Row], unresolved_count: int) -> DashboardMetrics:
        independent = [r for r in live_scored if r.forecast.is_independent]
        anchored = [r for r in live_scored if not r.forecast.is_independent]
        headline = [r for r in independent if _time_bucket(r.forecast) != "<1h"]

        user_briers = [float(r.score.user_brier) for r in headline]
        market_briers = [
            float(r.score.market_brier) for r in headline if r.score.market_brier is not None
        ]
        deltas = [
            float(r.score.brier_delta)
            for r in headline
            if r.score.brier_delta is not None
        ]
        pnl_total = round(sum(float(r.score.synthetic_pnl) for r in headline), 4)

        resolved_count = len(live_scored)
        return DashboardMetrics(
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
            headline_count=len(headline),
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
        independent = [
            r for r in live_scored if r.forecast.is_independent and _time_bucket(r.forecast) != "<1h"
        ]
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
                provisional=counts[cat] < 20,
            )
            for cat in sorted(counts)
        ]

    def _platform_breakdown(self, live_scored: list[_Row]) -> list[PlatformEdge]:
        by_platform: dict[object, list[float]] = {}
        counts: dict[object, int] = {}
        for r in live_scored:
            platform = r.forecast.platform
            counts[platform] = counts.get(platform, 0) + 1
            if r.forecast.is_independent and _time_bucket(r.forecast) != "<1h":
                if r.score.brier_delta is not None:
                    by_platform.setdefault(platform, []).append(float(r.score.brier_delta))
        return [
            PlatformEdge(
                platform=platform,
                count=counts[platform],
                mean_brier_delta=_mean(by_platform.get(platform, [])),
            )
            for platform in sorted(counts, key=lambda p: p.value)
        ]

    def _time_breakdown(self, live_scored: list[_Row]) -> list[TimeBucketEdge]:
        by_bucket: dict[str, list[float]] = {bucket: [] for bucket in TIME_BUCKETS}
        counts: dict[str, int] = {bucket: 0 for bucket in TIME_BUCKETS}
        for r in live_scored:
            bucket = _time_bucket(r.forecast)
            counts[bucket] += 1
            if r.forecast.is_independent and bucket != "<1h" and r.score.brier_delta is not None:
                by_bucket[bucket].append(float(r.score.brier_delta))
        return [
            TimeBucketEdge(
                bucket=bucket,
                count=counts[bucket],
                mean_brier_delta=_mean(by_bucket[bucket]),
            )
            for bucket in TIME_BUCKETS
        ]

    def _brier_trend(self, live_scored: list[_Row]) -> list[BrierTrendPoint]:
        headline = [
            r for r in live_scored if r.forecast.is_independent and _time_bucket(r.forecast) != "<1h"
        ]
        ordered = sorted(headline, key=lambda r: r.forecast.locked_at)
        return [
            BrierTrendPoint(
                seq=index,
                locked_at=r.forecast.locked_at,
                user_brier=float(r.score.user_brier),
                market_brier=(
                    float(r.score.market_brier) if r.score.market_brier is not None else None
                ),
            )
            for index, r in enumerate(ordered, start=1)
        ]


def _time_bucket(forecast: ForecastLog) -> str:
    seconds = forecast.time_to_resolution_seconds
    if seconds is None:
        return "unknown"
    if seconds >= 7 * 24 * 60 * 60:
        return "7d+"
    if seconds >= 24 * 60 * 60:
        return "1-7d"
    if seconds >= 6 * 60 * 60:
        return "6-24h"
    if seconds >= 60 * 60:
        return "1-6h"
    return "<1h"
