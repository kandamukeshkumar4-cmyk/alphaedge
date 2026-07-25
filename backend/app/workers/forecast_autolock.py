"""Bounded pre-close model forecast locking for external markets.

This worker moves the evaluation pipeline forward in time: it records a real
LIVE forecast while an external market is still open, then the existing venue
resolver and scoring leakage gate decide whether that forecast is gradeable.
It never resolves a market, backfills a prediction, or submits an order.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastSource,
    JobRun,
)
from app.forecasting.market_source import get_adapter
from app.services.forecast_service import ForecastService

logger = logging.getLogger(__name__)

FORECAST_AUTOLOCK_JOB_NAME = "forecast_autolock_task"
AUTOLOCK_FORECASTER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "alphaedge:model-autolock:v1")
DEFAULT_AUTOLOCK_BATCH_SIZE = 25
MAX_AUTOLOCK_BATCH_SIZE = 250
DEFAULT_AUTOLOCK_WINDOW_SEC = 24 * 60 * 60
_TERMINAL_SNAPSHOT_STATUSES = frozenset(
    {"closed", "resolved", "settled", "finalized", "determined", "ended"}
)


class _AutolockEligibilityLost(Exception):
    """The market ceased to be safely pre-close while the lock was in flight."""


def _unrecoverable_hash() -> str:
    """Create a credential hash with no retained or published raw credential."""
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


async def _system_forecaster(session: AsyncSession) -> Forecaster:
    forecaster = await session.get(Forecaster, AUTOLOCK_FORECASTER_ID)
    if forecaster is not None:
        return forecaster
    forecaster = Forecaster(
        id=AUTOLOCK_FORECASTER_ID,
        token_hash=_unrecoverable_hash(),
        recovery_code_hash=_unrecoverable_hash(),
    )
    session.add(forecaster)
    await session.flush()
    return forecaster


def _snapshot_is_open(metadata: dict[str, object] | None) -> bool:
    metadata = metadata or {}
    if metadata.get("closed") is True:
        return False
    status = str(metadata.get("status") or "").strip().lower()
    return status not in _TERMINAL_SNAPSHOT_STATUSES


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def autolock_forecasts(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_AUTOLOCK_BATCH_SIZE,
    window_sec: int = DEFAULT_AUTOLOCK_WINDOW_SEC,
) -> dict[str, int]:
    """Lock model forecasts for a bounded batch of genuinely pre-close markets."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    bounded_limit = min(max(int(limit), 1), MAX_AUTOLOCK_BATCH_SIZE)
    bounded_window_sec = max(int(window_sec), 1)
    horizon = now + timedelta(seconds=bounded_window_sec)

    live_forecast_exists = (
        select(ForecastLog.id)
        .where(
            ForecastLog.external_market_id == ExternalMarket.id,
            ForecastLog.mode == ForecastMode.LIVE,
        )
        .exists()
    )
    markets = (
        (
            await session.execute(
                select(ExternalMarket)
                .where(
                    ExternalMarket.status == ExternalMarketStatus.OPEN,
                    ExternalMarket.close_at.is_not(None),
                    ExternalMarket.close_at > now,
                    ExternalMarket.close_at <= horizon,
                    ~live_forecast_exists,
                )
                .order_by(ExternalMarket.close_at.asc(), ExternalMarket.id.asc())
                .limit(bounded_limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )

    locked = skipped = errors = 0
    forecaster: Forecaster | None = None
    service = ForecastService(session, correlation_id="worker:forecast-autolock")
    from app.forecasting.generic_artifact import (
        hours_to_resolution,
        load_active_generic_artifact,
    )

    # ACTIVE generic artifact only. Inactive registry rows are never loaded.
    active_artifact = await load_active_generic_artifact(session)
    for market in markets:
        try:
            adapter_snapshot = get_adapter(market.platform).fetch_snapshot(
                market.external_id
            )
            implied = adapter_snapshot.implied_probability
            if (
                not _snapshot_is_open(adapter_snapshot.metadata)
                or implied is None
                or not 0.0 <= float(implied) <= 1.0
            ):
                skipped += 1
                continue

            ttr_hours = hours_to_resolution(close_or_lock_at=market.close_at, now=now)
            category = (
                market.category.strip()
                if isinstance(market.category, str) and market.category.strip()
                else None
            )
            if active_artifact is None:
                prediction = ForecastService.predict(
                    market.external_id,
                    implied_yes=float(implied),
                )
            else:
                prediction = ForecastService.predict(
                    market.external_id,
                    implied_yes=float(implied),
                    artifact=active_artifact,
                    category=category,
                    time_to_resolution_hours=ttr_hours,
                )
            if prediction is None:
                skipped += 1
                continue

            if forecaster is None:
                forecaster = await _system_forecaster(session)
            metadata: dict[str, object] = dict(adapter_snapshot.metadata or {})
            metadata.update(
                {
                    "lock_origin": "model_autolock",
                    "model_provisional": prediction.provisional,
                    "clv_gate_passed": prediction.clv_gate_passed,
                    "selected_at": now.isoformat(),
                    "selection_window_sec": bounded_window_sec,
                }
            )
            async with session.begin_nested():
                persisted = await service.lock_forecast(
                    forecaster,
                    market,
                    prediction.model_prob,
                    float(implied),
                    snapshot_source=adapter_snapshot.source,
                    mode=ForecastMode.LIVE,
                    source=ForecastSource.WEB,
                    snapshot_metadata=metadata,
                    idempotency_key=f"model-autolock:{market.id}",
                    # V56: the provenance of the prediction that produced
                    # model_prob, written by the same INSERT inside this
                    # savepoint — an eligibility rollback takes it with the lock.
                    provenance=prediction.provenance,
                )
                # lock_forecast deliberately refreshes the venue snapshot. Re-check
                # that second read and the actual lock timestamp inside the savepoint
                # so a close/resolution race rolls back the forecast, snapshot, event.
                close_at = market.close_at
                if (
                    not _snapshot_is_open(persisted.snapshot_metadata)
                    or close_at is None
                    or _as_utc(persisted.locked_at) >= _as_utc(close_at)
                ):
                    raise _AutolockEligibilityLost
            locked += 1
            # Loop V49 E1/E2: observation hooks AFTER the savepoint commits so a
            # rolled-back eligibility loss never fans a phantom lock frame or
            # watcher notification. Both hooks are never-raises.
            try:
                from app.services.forecast_events import publish_forecast_locked
                from app.services.notification_producers import (
                    notify_watchers_forecast_locked,
                )

                await publish_forecast_locked(
                    forecast_id=persisted.id,
                    external_market_id=market.id,
                    platform=(
                        market.platform.value
                        if hasattr(market.platform, "value")
                        else str(market.platform)
                    ),
                    external_id=market.external_id,
                    title=market.title,
                    user_probability=persisted.user_probability,
                    market_implied_probability=persisted.market_implied_probability,
                    mode=(
                        persisted.mode.value
                        if hasattr(persisted.mode, "value")
                        else str(persisted.mode)
                    ),
                    locked_at=persisted.locked_at,
                )
                await notify_watchers_forecast_locked(
                    external_market=market,
                    forecast=persisted,
                    session=session,
                )
            except Exception:  # noqa: BLE001 — never-raises isolation
                logger.warning(
                    "forecast.locked publish/notify hook failed for %s",
                    market.external_id,
                    exc_info=True,
                )
        except _AutolockEligibilityLost:
            skipped += 1
        except Exception as exc:  # noqa: BLE001 - isolate each external market
            logger.warning(
                "forecast autolock failed for %s/%s: %s",
                market.platform.value,
                market.external_id,
                exc,
            )
            errors += 1

    return {
        "candidates": len(markets),
        "locked": locked,
        "skipped": skipped,
        "errors": errors,
    }


async def forecast_autolock_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint with a durable JobRun heartbeat for every enabled pass."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    if not settings.scheduler_external_autolock_enabled:
        return {
            "skipped": True,
            "reason": "SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED=false",
        }

    from app.observability.autolock_funnel import funnel_snapshot

    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    now = ctx.get("now")
    limit = int(ctx.get("limit", settings.external_autolock_batch))
    window_sec = int(
        ctx.get("window_sec", settings.external_autolock_window_sec)
    )
    async with session_factory() as session:
        try:
            # V33 B2'b: snapshot the funnel BEFORE the pass. Measured after, the
            # markets this pass just locked would already be excluded by
            # ~live_forecast_exists, so a healthy pass would misreport as starved.
            funnel = await funnel_snapshot(
                session,
                now=now or datetime.now(UTC),
                limit=min(max(limit, 1), MAX_AUTOLOCK_BATCH_SIZE),
                window_sec=max(window_sec, 1),
            )
            summary = await autolock_forecasts(
                session,
                now=now,
                limit=limit,
                window_sec=window_sec,
            )
            summary = {**summary, "funnel": funnel}
            session.add(
                JobRun(
                    job_name=FORECAST_AUTOLOCK_JOB_NAME,
                    status="degraded" if summary["errors"] else "success",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            return summary
        except Exception as exc:
            await session.rollback()
            session.add(
                JobRun(
                    job_name=FORECAST_AUTOLOCK_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
