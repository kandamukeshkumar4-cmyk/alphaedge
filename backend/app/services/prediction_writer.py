"""Loop107 — the missing production writer for ``prediction_logs``.

``PredictionLog`` is READ by eight API surfaces (assistant, desk, edge_history,
market_drivers, opportunities, routes, screener, watchlist) plus the eval
service, pods runner and ops alerts, but before this module NOTHING in the
production code path ever constructed one: the only non-test constructor was the
model class itself. Prod proved it — ``GET /api/v1/opportunities`` reported
``funnel.candidates_open=97`` with ``with_model_p=0`` and
``empty_reason="no_model_predictions"``.

What this writer does, and deliberately does NOT do:

* It **reuses the existing prediction path** — ``ForecastService.predict``
  (``app/services/forecast_service.py:93``) → ``predict_market``
  (``app/forecasting/predictor.py:60``). No new model is invented here.
* It is **pure quant**: no LLM, no NIM, no network model call. The only inputs
  are the catalog market row and its latest persisted odds snapshot.
* It writes **forward only**. There is no backfill: a historical row written
  today from data we hold today would be look-ahead fabrication, so past markets
  are never filled in.
* A row records **only what was knowable at prediction time** — market slug, the
  odds snapshot that fed it, the producing path, and the scheduled ``lock_at``.
  Resolution state (``winning_outcome``, ``resolved_at``, ``MarketResolution``)
  is never read and never written.
* It is **idempotent per (market, recency window)**: a slug that already has a
  prediction inside the window is skipped, so boot catch-up and a cron pass in
  the same window cannot double-write.
* It never imports ``RiskService`` or ``OrderBookService``: a prediction is a
  signal, never an order. PAPER_TRADING_ONLY is untouched.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRun, Market, MarketStatus, OddsSnapshot, PredictionLog
from app.services.forecast_service import ForecastService

logger = logging.getLogger(__name__)

PREDICTION_WRITER_JOB_NAME = "prediction_writer_task"

# A pass is bounded work: top-N OPEN markets by volume (the same liquidity proxy
# the catalog and the opportunity scanner already rank by).
DEFAULT_PREDICTION_BATCH = 50
MAX_PREDICTION_BATCH = 200

# Idempotency / freshness window. A slug predicted inside this window is left
# alone, so the 30-minute cadence writes at most one row per market per window.
DEFAULT_PREDICTION_WINDOW_SEC = 30 * 60


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _dec4(value: float) -> Decimal:
    return Decimal(str(round(float(value), 4))).quantize(Decimal("0.0001"))


async def _latest_odds_snapshot(
    session: AsyncSession, slug: str
) -> OddsSnapshot | None:
    return await session.scalar(
        select(OddsSnapshot)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc(), OddsSnapshot.id.desc())
        .limit(1)
    )


async def _slugs_predicted_since(
    session: AsyncSession, slugs: list[str], cutoff: datetime
) -> set[str]:
    if not slugs:
        return set()
    rows = await session.execute(
        select(PredictionLog.market_slug)
        .where(
            PredictionLog.market_slug.in_(slugs),
            PredictionLog.predicted_at >= cutoff,
        )
        .distinct()
    )
    return {row[0] for row in rows.all()}


async def write_model_predictions(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_PREDICTION_BATCH,
    window_sec: int = DEFAULT_PREDICTION_WINDOW_SEC,
) -> dict[str, int]:
    """Persist one ``PredictionLog`` per eligible OPEN market. Returns a funnel.

    Eligibility, in order: market is OPEN; it is not already locked out
    (``lock_at`` in the past — a locked market can no longer be traded, so a new
    prediction on it is noise); it has no prediction inside the recency window;
    and it has a persisted market-implied price to feed the predictor. A market
    failing any gate is counted, never faked.
    """
    now = _as_utc(now) or datetime.now(UTC)
    bounded_limit = min(max(int(limit), 1), MAX_PREDICTION_BATCH)
    bounded_window_sec = max(int(window_sec), 1)
    cutoff = now - timedelta(seconds=bounded_window_sec)

    markets = (
        (
            await session.execute(
                select(Market)
                .where(Market.status == MarketStatus.OPEN)
                .order_by(Market.volume.desc(), Market.slug.asc())
                .limit(bounded_limit)
            )
        )
        .scalars()
        .all()
    )

    funnel = {
        "candidates": len(markets),
        "eligible": 0,
        "written": 0,
        "skipped_locked_out": 0,
        "skipped_recent": 0,
        "skipped_no_market_price": 0,
        "errors": 0,
    }

    tradeable: list[Market] = []
    for market in markets:
        lock_at = _as_utc(market.lock_at)
        if lock_at is not None and lock_at <= now:
            funnel["skipped_locked_out"] += 1
            continue
        tradeable.append(market)

    recent = await _slugs_predicted_since(
        session, [market.slug for market in tradeable], cutoff
    )

    for market in tradeable:
        if market.slug in recent:
            funnel["skipped_recent"] += 1
            continue
        funnel["eligible"] += 1
        try:
            snapshot = await _latest_odds_snapshot(session, market.slug)
            if snapshot is None or snapshot.implied_yes is None:
                funnel["skipped_no_market_price"] += 1
                continue
            implied = float(snapshot.implied_yes)
            if not 0.0 <= implied <= 1.0:
                funnel["skipped_no_market_price"] += 1
                continue

            prediction = ForecastService.predict(market.slug, implied_yes=implied)
            if prediction is None:
                funnel["errors"] += 1
                continue

            provenance = prediction.provenance
            session.add(
                PredictionLog(
                    market_id=market.id,
                    market_slug=market.slug,
                    predicted_prob=_dec4(prediction.model_prob),
                    # Provisional until the CLV gate proves the edge; the gate
                    # result is recorded, never assumed.
                    confidence=_dec4(0.75 if prediction.clv_gate_passed else 0.5),
                    odds_snapshot_id=snapshot.id,
                    input_feature_hash=provenance.feature_schema_digest,
                    explanation={
                        # Only prediction-time facts. No outcome, no resolution.
                        "writer": "prediction_writer",
                        "producer": provenance.model_type,
                        "market_implied": round(implied, 4),
                        "odds_source": snapshot.source,
                        "clv_gate_passed": prediction.clv_gate_passed,
                        "provisional": prediction.provisional,
                        "feature_schema_digest": provenance.feature_schema_digest,
                    },
                    predicted_at=now,
                    lock_at=market.lock_at,
                )
            )
            funnel["written"] += 1
        except Exception as exc:  # noqa: BLE001 — isolate one market, keep the pass
            logger.warning(
                "prediction writer failed for %s: %s", market.slug, exc, exc_info=True
            )
            funnel["errors"] += 1

    await session.flush()
    return funnel


async def prediction_writer_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ / in-process entrypoint with a durable JobRun heartbeat per pass."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    if not settings.scheduler_prediction_writer_enabled:
        return {"skipped": True, "reason": "SCHEDULER_PREDICTION_WRITER_ENABLED=false"}

    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    limit = int(ctx.get("limit", settings.prediction_writer_batch))
    window_sec = int(ctx.get("window_sec", settings.prediction_writer_window_sec))
    async with session_factory() as session:
        try:
            summary = await write_model_predictions(
                session,
                now=ctx.get("now"),
                limit=limit,
                window_sec=window_sec,
            )
            session.add(
                JobRun(
                    job_name=PREDICTION_WRITER_JOB_NAME,
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
                    job_name=PREDICTION_WRITER_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
