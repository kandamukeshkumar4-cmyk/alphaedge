from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastSource,
    MarketSnapshot,
    Platform,
)
from app.events.bus import DomainEventBus
from app.forecasting import scoring
from app.forecasting.market_source import get_adapter


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class ForecastService:
    """Locks immutable forecasts. Each lock is append-only; a forecaster can lock
    again on the same market to record a belief update (a new seq)."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def lock_forecast(
        self,
        forecaster: Forecaster,
        external_market: ExternalMarket,
        user_probability: float,
        market_implied_probability: float | None,
        snapshot_source: str = "manual",
        mode: ForecastMode = ForecastMode.LIVE,
        source: ForecastSource = ForecastSource.WEB,
        outcome_label: str = "YES",
        snapshot_metadata: dict[str, object] | None = None,
    ) -> ForecastLog:
        if not 0.0 <= user_probability <= 1.0:
            raise ValueError("user_probability must be in [0, 1]")
        if market_implied_probability is not None and not 0.0 <= market_implied_probability <= 1.0:
            raise ValueError("market_implied_probability must be in [0, 1]")

        if mode == ForecastMode.LIVE and external_market.status != ExternalMarketStatus.OPEN:
            raise ValueError("LIVE forecasts can only be locked on open markets")
        if mode == ForecastMode.PRACTICE and external_market.status != ExternalMarketStatus.RESOLVED:
            raise ValueError("PRACTICE forecasts require an already-resolved market")

        latest = await self._latest(forecaster.id, external_market.id)
        if latest is not None and abs(float(latest.user_probability) - user_probability) < 1e-9:
            raise ValueError("redundant lock: probability unchanged from your last lock")

        next_seq = (latest.seq + 1) if latest is not None else 1
        locked_at = datetime.now(timezone.utc)
        effective_implied = market_implied_probability
        effective_source = snapshot_source
        effective_metadata: dict[str, object] = dict(snapshot_metadata or {})

        adapter = get_adapter(external_market.platform)
        adapter_snapshot = adapter.fetch_snapshot(external_market.external_id)
        if external_market.platform in (Platform.POLYMARKET, Platform.KALSHI):
            adapter_metadata = adapter_snapshot.metadata or {}
            if adapter_snapshot.implied_probability is not None:
                effective_implied = adapter_snapshot.implied_probability
                effective_source = adapter_snapshot.source
            if adapter_metadata and adapter_metadata.get("status") != "unavailable":
                effective_source = adapter_snapshot.source
                effective_metadata.update(adapter_metadata)

        snapshot = MarketSnapshot(
            external_market_id=external_market.id,
            platform=external_market.platform,
            implied_probability=_dec(effective_implied) if effective_implied is not None else None,
            source=effective_source,
            snapshot_metadata=effective_metadata,
            captured_at=locked_at,
        )
        self.session.add(snapshot)
        await self.session.flush()

        ttr_seconds: int | None = None
        close_at = _as_utc(external_market.close_at)
        if close_at is not None:
            ttr_seconds = int((close_at - locked_at).total_seconds())

        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=external_market.id,
            market_snapshot_id=snapshot.id,
            seq=next_seq,
            platform=external_market.platform,
            market_url=external_market.url,
            outcome_label=outcome_label,
            user_probability=_dec(user_probability),
            market_implied_probability=(
                _dec(effective_implied)
                if effective_implied is not None
                else None
            ),
            snapshot_source=effective_source,
            is_independent=scoring.is_independent(
                user_probability, effective_implied
            ),
            mode=mode,
            source=source,
            snapshot_metadata=effective_metadata,
            time_to_resolution_seconds=ttr_seconds,
            locked_at=locked_at,
        )
        self.session.add(forecast)
        await self.session.flush()
        await self.events.emit(
            "forecast_locked",
            {
                "forecast_id": str(forecast.id),
                "forecaster_id": str(forecaster.id),
                "external_market_id": str(external_market.id),
                "seq": next_seq,
                "mode": mode.value,
                "is_independent": forecast.is_independent,
            },
        )
        return forecast

    async def _latest(self, forecaster_id, external_market_id) -> ForecastLog | None:
        result = await self.session.execute(
            select(ForecastLog)
            .where(
                ForecastLog.forecaster_id == forecaster_id,
                ForecastLog.external_market_id == external_market_id,
            )
            .order_by(ForecastLog.seq.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _dec(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))
