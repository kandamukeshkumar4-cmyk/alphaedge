from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SignalEvent

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
    ForecastLifecycleItem,
    ForecastLifecycleResponse,
    PlatformEdge,
    PracticeMetrics,
    TimeBucketEdge,
)

TIME_BUCKETS = ("7d+", "1-7d", "6-24h", "1-6h", "<1h", "unknown")

CLV_PROVISIONAL_SAMPLE = 30
PAPER_PNL_NOTE = "paper-only"
SIGNAL_DISCLAIMER = (
    "Research only — not financial advice. Verify resolution terms. Paper trading only."
)


@dataclass(frozen=True)
class CLVRecord:
    market_slug: str
    model_prob: float
    closing_prob: float | None
    clv: float | None
    resolved_at: datetime | None
    is_edge: bool


@dataclass(frozen=True)
class SignalFeedItem:
    id: str
    signal_type: str
    platform: str
    market_id: str
    market_name: str
    implied_edge: float | None
    sample_size: int
    is_edge: bool
    created_at: datetime
    resolved: bool


class CLVTrackingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_clv_track_record(self, limit: int = 100) -> list[CLVRecord]:
        result = await self.session.execute(
            select(SignalEvent).order_by(SignalEvent.created_at.desc())
        )
        records: list[CLVRecord] = []
        for event in result.scalars().all():
            tracking = _tracking_payload(event)
            if not tracking.get("resolved"):
                continue
            record = _clv_record_from_event(event, tracking)
            if record is not None:
                records.append(record)
        records.sort(key=lambda row: row.resolved_at or datetime.min, reverse=True)
        return records[:limit]

    async def get_paper_pnl_summary(self) -> dict[str, Any]:
        records = await self.get_clv_track_record(limit=10_000)
        pnls = [_paper_pnl_for_record(record) for record in records]
        wins = sum(1 for pnl in pnls if pnl > 0)
        n_bets = len(pnls)
        total_pnl = round(sum(pnls), 4)
        win_rate = round(wins / n_bets, 4) if n_bets else 0.0
        return {
            "total_pnl": total_pnl,
            "n_bets": n_bets,
            "win_rate": win_rate,
            "note": PAPER_PNL_NOTE,
            "disclaimer": SIGNAL_DISCLAIMER,
            "paper_trading_only": True,
        }

    async def get_signal_feed(self, limit: int = 50) -> list[SignalFeedItem]:
        result = await self.session.execute(
            select(SignalEvent).order_by(SignalEvent.created_at.desc()).limit(limit)
        )
        return [_signal_feed_item(event) for event in result.scalars().all()]


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

    async def lifecycle(self, forecaster_id: UUID) -> ForecastLifecycleResponse:
        result = await self.session.execute(
            select(ForecastLog, ForecastScore, ExternalMarket)
            .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
            .outerjoin(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
            .where(ForecastLog.forecaster_id == forecaster_id)
            .order_by(ForecastLog.locked_at.desc())
        )
        rows = [_Row(f, s, m) for f, s, m in result.all() if f.mode == ForecastMode.LIVE]
        unresolved = [
            r
            for r in rows
            if r.score is None and r.market.status != ExternalMarketStatus.RESOLVED
        ]
        recently_resolved = [
            r
            for r in rows
            if r.score is not None and r.market.status == ExternalMarketStatus.RESOLVED
        ]
        recently_resolved = sorted(
            recently_resolved,
            key=lambda row: row.market.resolved_at or row.forecast.locked_at,
            reverse=True,
        )
        return ForecastLifecycleResponse(
            unresolved_count=len(unresolved),
            recently_resolved_count=len(recently_resolved),
            unresolved=[_lifecycle_item(row, "unresolved") for row in unresolved[:50]],
            recently_resolved=[
                _lifecycle_item(row, "resolved") for row in recently_resolved[:25]
            ],
        )

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


def _lifecycle_item(row: _Row, status: str) -> ForecastLifecycleItem:
    score = row.score
    return ForecastLifecycleItem(
        forecast_id=row.forecast.id,
        external_market_id=row.market.id,
        platform=row.forecast.platform,
        title=row.market.title,
        url=row.market.url,
        outcome_label=row.forecast.outcome_label,
        user_probability=float(row.forecast.user_probability),
        market_implied_probability=(
            float(row.forecast.market_implied_probability)
            if row.forecast.market_implied_probability is not None
            else None
        ),
        locked_at=row.forecast.locked_at,
        status=status,
        user_brier=float(score.user_brier) if score is not None else None,
        brier_delta=float(score.brier_delta) if score is not None and score.brier_delta is not None else None,
        synthetic_pnl=float(score.synthetic_pnl) if score is not None else None,
        resolved_at=row.market.resolved_at,
    )


def _tracking_payload(event: SignalEvent) -> dict[str, Any]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    tracking = payload.get("tracking")
    if isinstance(tracking, dict):
        merged = {**payload, **tracking}
        merged["resolved"] = tracking.get("resolved", payload.get("resolved", False))
        return merged
    return payload


def _clv_record_from_event(event: SignalEvent, tracking: dict[str, Any]) -> CLVRecord | None:
    model_prob = _optional_float(
        tracking.get("model_prob", tracking.get("model_probability", tracking.get("predicted_prob")))
    )
    if model_prob is None:
        return None
    closing_prob = _optional_float(
        tracking.get("closing_prob", tracking.get("closing_probability", tracking.get("closing_implied")))
    )
    clv = _optional_float(tracking.get("clv"))
    if clv is None and closing_prob is not None:
        clv = round(model_prob - closing_prob, 6)
    resolved_at = _parse_datetime(
        tracking.get("resolved_at") or tracking.get("resolvedAt")
    )
    market_slug = str(
        tracking.get("market_slug")
        or tracking.get("market_name")
        or f"{event.platform}/{event.market_id}"
    )
    return CLVRecord(
        market_slug=market_slug,
        model_prob=model_prob,
        closing_prob=closing_prob,
        clv=clv,
        resolved_at=resolved_at,
        is_edge=bool(tracking.get("is_edge", False)),
    )


def _signal_feed_item(event: SignalEvent) -> SignalFeedItem:
    payload = event.payload if isinstance(event.payload, dict) else {}
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else payload
    tracking = _tracking_payload(event)
    sample_size = int(tracking.get("sample_size", tracking.get("trade_count", 0)) or 0)
    implied_edge = _signal_implied_edge(event.signal_type, signal, tracking)
    is_edge = bool(tracking.get("is_edge", _signal_is_edge(event.signal_type, signal)))
    market_name = str(
        tracking.get("market_slug")
        or tracking.get("market_name")
        or signal.get("title")
        or event.market_id
    )
    return SignalFeedItem(
        id=str(event.id),
        signal_type=event.signal_type,
        platform=event.platform,
        market_id=event.market_id,
        market_name=market_name,
        implied_edge=implied_edge,
        sample_size=sample_size,
        is_edge=is_edge,
        created_at=event.created_at,
        resolved=bool(tracking.get("resolved", False)),
    )


def _signal_implied_edge(
    signal_type: str,
    signal: dict[str, Any],
    tracking: dict[str, Any],
) -> float | None:
    if tracking.get("edge") is not None:
        return _optional_float(tracking.get("edge"))
    if signal_type == "arbitrage":
        return _optional_float(signal.get("net_spread"))
    if signal_type == "dutching":
        return_pct = _optional_float(signal.get("return_pct"))
        if return_pct is not None:
            return round(return_pct / 100.0, 6)
        return _optional_float(signal.get("profit"))
    if signal_type == "forecast":
        return _optional_float(tracking.get("clv") or signal.get("edge"))
    return None


def _signal_is_edge(signal_type: str, signal: dict[str, Any]) -> bool:
    if signal_type == "arbitrage":
        return bool(signal.get("is_arbitrage") and signal.get("headline_eligible"))
    if signal_type == "dutching":
        return bool(signal.get("risk_free"))
    if signal_type == "forecast":
        return bool(signal.get("is_edge"))
    return bool(signal.get("headline_eligible"))


def _paper_pnl_for_record(record: CLVRecord) -> float:
    if record.clv is None:
        return 0.0
    stake = 100.0
    return round(record.clv * stake, 4)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
