from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

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
from app.forecasting.predictor import ForecastPrediction, predict_market

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ForecastProvenance:
    """What actually produced a locked probability, recorded at lock time.

    Loop V56. Every field is optional and a null is never guessed away:
    ``artifact_digest``/``model_version`` stay None whenever the model registry
    could not supply them, which is the honest record and is counted rather than
    filled in. ``model_type`` names the *producing* path (see predictor
    PRODUCER_* constants), not ``settings.ml_model_type`` — today's lock path
    supplies no artifact, so no ML model runs and stamping "xgboost" here would
    be a fabrication.
    """

    model_type: str | None = None
    model_version: str | None = None
    artifact_digest: str | None = None
    feature_schema_digest: str | None = None
    feature_payload: dict[str, object] | None = None


@dataclass(frozen=True)
class MarketDetailForecastResult:
    model_prob: float
    clv_gate_passed: bool
    provisional: bool
    provenance: ForecastProvenance = ForecastProvenance()


def feature_schema_digest(payload: Mapping[str, object]) -> str:
    """Stable digest of the feature *names* handed to the predictor.

    Keys only: this identifies the feature schema across locks, while the values
    live in ``feature_payload``.
    """
    canonical = ",".join(sorted(str(key) for key in payload))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _jsonable(value: object) -> object:
    """Reduce a feature value to something JSON can hold, without inventing data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


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

    @staticmethod
    def predict(slug: str, implied_yes: float = 0.5) -> MarketDetailForecastResult | None:
        """Return a paper forecast for catalog markets when the predictor is available."""
        # The exact payload handed to the predictor, captured before the call so
        # the provenance records what was actually sent rather than a rebuild.
        features: dict[str, object] = {
            "market_slug": slug,
            "implied_yes": implied_yes,
            "market_implied": implied_yes,
        }
        try:
            prediction = predict_market(features)
        except Exception:
            logger.exception("ForecastService.predict failed for slug=%s", slug)
            return None

        clv_gate_passed = (
            prediction.evaluation is not None
            and prediction.evaluation.model_beats_closing
        )
        return MarketDetailForecastResult(
            model_prob=round(prediction.predicted_prob, 4),
            clv_gate_passed=clv_gate_passed,
            provisional=not clv_gate_passed,
            provenance=ForecastService._provenance(prediction, features),
        )

    @staticmethod
    def _provenance(
        prediction: ForecastPrediction, features: Mapping[str, object]
    ) -> ForecastProvenance:
        """Describe the producing model without ever inventing an identifier.

        The registry is not consulted by the lock path today: no caller supplies
        ``model_artifact_path``, so ``predict_market`` loads no artifact and
        there is no digest or version to read. Those stay None and are counted
        by the A/B preflight (V56 P3) instead of being filled from
        ``settings.ml_model_type``, which would attribute a market-implied
        passthrough to a model that never ran.
        """
        return ForecastProvenance(
            model_type=prediction.producer,
            model_version=None,
            artifact_digest=None,
            feature_schema_digest=feature_schema_digest(features),
            feature_payload={key: _jsonable(value) for key, value in features.items()},
        )

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
        idempotency_key: str | None = None,
        provenance: ForecastProvenance | None = None,
    ) -> ForecastLog:
        if idempotency_key:
            existing = await self._get_by_idempotency_key(forecaster.id, idempotency_key)
            if existing is not None:
                return existing

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
            idempotency_key=idempotency_key,
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
            # V56: provenance rides on the forecast row itself, so it is written
            # by the same INSERT as the lock and cannot survive a rollback of it.
            # A caller that supplies none leaves every column null (unknown).
            model_type=provenance.model_type if provenance else None,
            model_version=provenance.model_version if provenance else None,
            artifact_digest=provenance.artifact_digest if provenance else None,
            feature_schema_digest=provenance.feature_schema_digest if provenance else None,
            feature_payload=provenance.feature_payload if provenance else None,
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

    async def _get_by_idempotency_key(
        self, forecaster_id, idempotency_key: str
    ) -> ForecastLog | None:
        result = await self.session.execute(
            select(ForecastLog)
            .where(
                ForecastLog.forecaster_id == forecaster_id,
                ForecastLog.idempotency_key == idempotency_key,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


def _dec(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))
