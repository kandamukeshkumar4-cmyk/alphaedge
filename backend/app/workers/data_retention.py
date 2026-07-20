"""Loop V39/V70 — data retention sweeps.

Consumer-aware policy (see goals/loop-v39-retention/STATE.md R1 audit):

* ``odds_snapshots``: full resolution for ``ODDS_SNAPSHOT_FULL_RES_DAYS`` (default
  90); older ticks are **downsampled** to one daily close per
  (market_slug, source, UTC day). Never deletes rows referenced by
  ``prediction_logs.odds_snapshot_id`` (CLV/scoring FK). Never touches rows
  inside the full-res window.
* ``signal_events``: hard prune older than ``SIGNAL_EVENT_RETENTION_DAYS``
  (default 30).
* ``notifications``: delete only **read** rows older than
  ``NOTIFICATION_RETENTION_DAYS`` (default 90); unread kept forever.

Loop V70 high-growth tables (age + row-cap, FK-safe batch deletes):

* ``whale_events``, ``market_sentiment_snapshots``, ``heartbeat_decision_logs``,
  ``pod_trades``: retain at most 14 days and at most 500k newest rows per table
  (age prune then row-cap prune). Batched deletes; no inbound FKs on these
  tables so deletes are FK-safe.

Flag-gated (``DATA_RETENTION_ENABLED``, default on). Batched, idempotent
deletes. Dual-wired: ARQ cron in ``workers/tasks.py`` + in-process loop in
``main.py``. Heartbeat name: ``data_retention``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    HeartbeatDecisionLog,
    JobRun,
    MarketSentimentSnapshot,
    Notification,
    OddsSnapshot,
    PodTrade,
    PredictionLog,
    SignalEvent,
    WhaleEvent,
)

DATA_RETENTION_JOB_NAME = "data_retention_task"

DEFAULT_FULL_RES_DAYS = 90
DEFAULT_SIGNAL_EVENT_DAYS = 30
DEFAULT_NOTIFICATION_DAYS = 90
DEFAULT_HIGH_GROWTH_DAYS = 14
DEFAULT_HIGH_GROWTH_MAX_ROWS = 500_000
DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 2000
MAX_BATCHES_PER_PASS = 20
MAX_MARKET_PAIRS_PER_PASS = 50


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _utc_day(ts: datetime) -> date:
    return _as_utc(ts).date()


async def _protected_odds_snapshot_ids(session: AsyncSession) -> set[UUID]:
    """IDs referenced by prediction_logs — never delete (CLV/scoring FK)."""
    rows = (
        await session.execute(
            select(PredictionLog.odds_snapshot_id).where(
                PredictionLog.odds_snapshot_id.is_not(None)
            )
        )
    ).scalars().all()
    return {rid for rid in rows if rid is not None}


async def sweep_odds_snapshots_downsample(
    session: AsyncSession,
    *,
    full_res_days: int = DEFAULT_FULL_RES_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
    max_pairs: int = MAX_MARKET_PAIRS_PER_PASS,
) -> dict[str, Any]:
    """Downsample old odds_snapshots to daily closes; leave full-res window intact.

    Idempotent: a second pass finds no intermediate ticks to drop.
    """
    now = _as_utc(now or datetime.now(UTC))
    days = max(1, int(full_res_days))
    bound = min(max(int(batch_size), 1), MAX_BATCH_SIZE)
    batches = min(max(int(max_batches), 1), MAX_BATCHES_PER_PASS)
    pairs_cap = min(max(int(max_pairs), 1), MAX_MARKET_PAIRS_PER_PASS)
    cutoff = now - timedelta(days=days)

    protected = await _protected_odds_snapshot_ids(session)

    pair_rows = (
        await session.execute(
            select(OddsSnapshot.market_slug, OddsSnapshot.source)
            .where(OddsSnapshot.captured_at < cutoff)
            .distinct()
            .limit(pairs_cap)
        )
    ).all()

    deleted = 0
    batches_run = 0
    pairs_seen = 0

    for market_slug, source in pair_rows:
        pairs_seen += 1
        old_rows = (
            await session.execute(
                select(
                    OddsSnapshot.id,
                    OddsSnapshot.captured_at,
                )
                .where(
                    OddsSnapshot.market_slug == market_slug,
                    OddsSnapshot.source == source,
                    OddsSnapshot.captured_at < cutoff,
                )
                .order_by(OddsSnapshot.captured_at.asc())
            )
        ).all()
        if not old_rows:
            continue

        by_day: dict[date, list[tuple[UUID, datetime]]] = defaultdict(list)
        for sid, captured_at in old_rows:
            by_day[_utc_day(captured_at)].append((sid, captured_at))

        keep: set[UUID] = set()
        for day_rows in by_day.values():
            # Daily close = last tick of the UTC day.
            best_id = max(day_rows, key=lambda item: _as_utc(item[1]))[0]
            keep.add(best_id)

        deletable = [
            sid
            for sid, _ in old_rows
            if sid not in keep and sid not in protected
        ]
        if not deletable:
            continue

        idx = 0
        while idx < len(deletable) and batches_run < batches:
            chunk = deletable[idx : idx + bound]
            idx += bound
            result = await session.execute(
                delete(OddsSnapshot).where(OddsSnapshot.id.in_(chunk))
            )
            deleted += int(result.rowcount or 0)
            batches_run += 1
            await session.flush()
            if batches_run >= batches:
                break
        if batches_run >= batches:
            break

    return {
        "deleted": deleted,
        "batches": batches_run,
        "pairs_seen": pairs_seen,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "full_res_days": days,
        "batch_size": bound,
        "protected_ids": len(protected),
    }


async def sweep_signal_events(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_SIGNAL_EVENT_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    """Delete signal_events older than retention_days (batched, idempotent)."""
    now = _as_utc(now or datetime.now(UTC))
    days = max(1, int(retention_days))
    bound = min(max(int(batch_size), 1), MAX_BATCH_SIZE)
    batches = min(max(int(max_batches), 1), MAX_BATCHES_PER_PASS)
    cutoff = now - timedelta(days=days)

    deleted = 0
    batches_run = 0
    for _ in range(batches):
        ids = list(
            (
                await session.execute(
                    select(SignalEvent.id)
                    .where(SignalEvent.created_at < cutoff)
                    .order_by(SignalEvent.created_at.asc())
                    .limit(bound)
                )
            )
            .scalars()
            .all()
        )
        if not ids:
            break
        result = await session.execute(
            delete(SignalEvent).where(SignalEvent.id.in_(ids))
        )
        deleted += int(result.rowcount or 0)
        batches_run += 1
        await session.flush()
        if len(ids) < bound:
            break

    return {
        "deleted": deleted,
        "batches": batches_run,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "retention_days": days,
        "batch_size": bound,
    }


async def sweep_notifications(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_NOTIFICATION_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    """Delete read notifications older than retention_days; never touch unread."""
    now = _as_utc(now or datetime.now(UTC))
    days = max(1, int(retention_days))
    bound = min(max(int(batch_size), 1), MAX_BATCH_SIZE)
    batches = min(max(int(max_batches), 1), MAX_BATCHES_PER_PASS)
    cutoff = now - timedelta(days=days)

    deleted = 0
    batches_run = 0
    for _ in range(batches):
        ids = list(
            (
                await session.execute(
                    select(Notification.id)
                    .where(
                        Notification.read_at.is_not(None),
                        Notification.created_at < cutoff,
                    )
                    .order_by(Notification.created_at.asc())
                    .limit(bound)
                )
            )
            .scalars()
            .all()
        )
        if not ids:
            break
        result = await session.execute(
            delete(Notification).where(Notification.id.in_(ids))
        )
        deleted += int(result.rowcount or 0)
        batches_run += 1
        await session.flush()
        if len(ids) < bound:
            break

    return {
        "deleted": deleted,
        "batches": batches_run,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "retention_days": days,
        "batch_size": bound,
    }


async def _batch_delete_ids(
    session: AsyncSession,
    model: type,
    id_col: Any,
    id_select,
    *,
    bound: int,
    batches: int,
    batches_run: int,
    deleted: int,
) -> tuple[int, int]:
    """Run up to remaining batches of id-selected deletes. Returns (deleted, batches_run)."""
    remaining = batches - batches_run
    for _ in range(remaining):
        ids = list((await session.execute(id_select.limit(bound))).scalars().all())
        if not ids:
            break
        result = await session.execute(delete(model).where(id_col.in_(ids)))
        deleted += int(result.rowcount or 0)
        batches_run += 1
        await session.flush()
        if len(ids) < bound:
            break
    return deleted, batches_run


async def sweep_age_and_row_cap(
    session: AsyncSession,
    model: type,
    *,
    ts_column_name: str = "created_at",
    retention_days: int = DEFAULT_HIGH_GROWTH_DAYS,
    max_rows: int = DEFAULT_HIGH_GROWTH_MAX_ROWS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    """Age-prune then row-cap prune for a high-growth append-only table.

    1. Delete rows with timestamp < now - retention_days (batched).
    2. If row count still exceeds max_rows, delete oldest until under the cap.

    FK-safe for observation tables with no inbound foreign keys.
    """
    now = _as_utc(now or datetime.now(UTC))
    days = max(1, int(retention_days))
    cap = max(1, int(max_rows))
    bound = min(max(int(batch_size), 1), MAX_BATCH_SIZE)
    batches = min(max(int(max_batches), 1), MAX_BATCHES_PER_PASS)
    cutoff = now - timedelta(days=days)

    id_col = model.id
    ts_col = getattr(model, ts_column_name)

    deleted = 0
    batches_run = 0

    age_select = (
        select(id_col).where(ts_col < cutoff).order_by(ts_col.asc(), id_col.asc())
    )
    deleted, batches_run = await _batch_delete_ids(
        session,
        model,
        id_col,
        age_select,
        bound=bound,
        batches=batches,
        batches_run=batches_run,
        deleted=deleted,
    )

    age_deleted = deleted

    if batches_run < batches:
        total_rows = int(
            await session.scalar(select(func.count()).select_from(model)) or 0
        )
        if total_rows > cap:
            # Oldest first until at most `cap` remain.
            # Delete ids that would rank beyond the newest `cap` rows.
            cap_select = select(id_col).order_by(ts_col.asc(), id_col.asc())
            # Only delete the excess: we keep selecting from the oldest end.
            excess = total_rows - cap
            while batches_run < batches and excess > 0:
                chunk = min(bound, excess)
                ids = list(
                    (
                        await session.execute(cap_select.limit(chunk))
                    )
                    .scalars()
                    .all()
                )
                if not ids:
                    break
                result = await session.execute(delete(model).where(id_col.in_(ids)))
                n = int(result.rowcount or 0)
                deleted += n
                batches_run += 1
                excess -= n
                await session.flush()
                if n < chunk:
                    break

    return {
        "deleted": deleted,
        "age_deleted": age_deleted,
        "cap_deleted": deleted - age_deleted,
        "batches": batches_run,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "retention_days": days,
        "max_rows": cap,
        "batch_size": bound,
        "table": getattr(model, "__tablename__", getattr(model, "__name__", "unknown")),
    }


async def sweep_whale_events(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_HIGH_GROWTH_DAYS,
    max_rows: int = DEFAULT_HIGH_GROWTH_MAX_ROWS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    return await sweep_age_and_row_cap(
        session,
        WhaleEvent,
        ts_column_name="captured_at",
        retention_days=retention_days,
        max_rows=max_rows,
        batch_size=batch_size,
        now=now,
        max_batches=max_batches,
    )


async def sweep_market_sentiment_snapshots(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_HIGH_GROWTH_DAYS,
    max_rows: int = DEFAULT_HIGH_GROWTH_MAX_ROWS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    return await sweep_age_and_row_cap(
        session,
        MarketSentimentSnapshot,
        ts_column_name="captured_at",
        retention_days=retention_days,
        max_rows=max_rows,
        batch_size=batch_size,
        now=now,
        max_batches=max_batches,
    )


async def sweep_heartbeat_decision_logs(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_HIGH_GROWTH_DAYS,
    max_rows: int = DEFAULT_HIGH_GROWTH_MAX_ROWS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    return await sweep_age_and_row_cap(
        session,
        HeartbeatDecisionLog,
        ts_column_name="created_at",
        retention_days=retention_days,
        max_rows=max_rows,
        batch_size=batch_size,
        now=now,
        max_batches=max_batches,
    )


async def sweep_pod_trades(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_HIGH_GROWTH_DAYS,
    max_rows: int = DEFAULT_HIGH_GROWTH_MAX_ROWS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    return await sweep_age_and_row_cap(
        session,
        PodTrade,
        ts_column_name="created_at",
        retention_days=retention_days,
        max_rows=max_rows,
        batch_size=batch_size,
        now=now,
        max_batches=max_batches,
    )


async def run_data_retention_sweeps(
    session: AsyncSession,
    *,
    full_res_days: int = DEFAULT_FULL_RES_DAYS,
    signal_event_days: int = DEFAULT_SIGNAL_EVENT_DAYS,
    notification_days: int = DEFAULT_NOTIFICATION_DAYS,
    high_growth_days: int = DEFAULT_HIGH_GROWTH_DAYS,
    high_growth_max_rows: int = DEFAULT_HIGH_GROWTH_MAX_ROWS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    odds_enabled: bool = True,
    signals_enabled: bool = True,
    notifications_enabled: bool = True,
    high_growth_enabled: bool = True,
) -> dict[str, Any]:
    """Run all enabled table sweeps; returns a combined summary."""
    now = _as_utc(now or datetime.now(UTC))
    summary: dict[str, Any] = {
        "odds_snapshots": None,
        "signal_events": None,
        "notifications": None,
        "whale_events": None,
        "market_sentiment_snapshots": None,
        "heartbeat_decision_logs": None,
        "pod_trades": None,
        "deleted_total": 0,
    }
    if odds_enabled:
        odds = await sweep_odds_snapshots_downsample(
            session,
            full_res_days=full_res_days,
            batch_size=batch_size,
            now=now,
        )
        summary["odds_snapshots"] = odds
        summary["deleted_total"] += int(odds.get("deleted") or 0)
    if signals_enabled:
        sigs = await sweep_signal_events(
            session,
            retention_days=signal_event_days,
            batch_size=batch_size,
            now=now,
        )
        summary["signal_events"] = sigs
        summary["deleted_total"] += int(sigs.get("deleted") or 0)
    if notifications_enabled:
        notes = await sweep_notifications(
            session,
            retention_days=notification_days,
            batch_size=batch_size,
            now=now,
        )
        summary["notifications"] = notes
        summary["deleted_total"] += int(notes.get("deleted") or 0)
    if high_growth_enabled:
        for key, sweep_fn in (
            ("whale_events", sweep_whale_events),
            ("market_sentiment_snapshots", sweep_market_sentiment_snapshots),
            ("heartbeat_decision_logs", sweep_heartbeat_decision_logs),
            ("pod_trades", sweep_pod_trades),
        ):
            result = await sweep_fn(
                session,
                retention_days=high_growth_days,
                max_rows=high_growth_max_rows,
                batch_size=batch_size,
                now=now,
            )
            summary[key] = result
            summary["deleted_total"] += int(result.get("deleted") or 0)
    return summary


async def data_retention_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint (+ in-process loop caller) with JobRun heartbeat."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    started_at = datetime.now(UTC)
    settings = ctx.get("settings") or get_settings()
    session_factory = ctx.get("session_factory") or AsyncSessionLocal

    if not getattr(settings, "data_retention_enabled", True):
        return {
            "deleted_total": 0,
            "skipped": True,
            "reason": "DATA_RETENTION_ENABLED=false",
        }

    full_res_days = int(
        ctx.get("full_res_days")
        or getattr(settings, "odds_snapshot_full_res_days", DEFAULT_FULL_RES_DAYS)
    )
    signal_event_days = int(
        ctx.get("signal_event_days")
        or getattr(settings, "signal_event_retention_days", DEFAULT_SIGNAL_EVENT_DAYS)
    )
    notification_days = int(
        ctx.get("notification_days")
        or getattr(settings, "notification_retention_days", DEFAULT_NOTIFICATION_DAYS)
    )
    batch_size = int(ctx.get("batch_size", DEFAULT_BATCH_SIZE))
    now = ctx.get("now")

    async with session_factory() as session:
        try:
            summary = await run_data_retention_sweeps(
                session,
                full_res_days=full_res_days,
                signal_event_days=signal_event_days,
                notification_days=notification_days,
                batch_size=batch_size,
                now=now,
            )
            session.add(
                JobRun(
                    job_name=DATA_RETENTION_JOB_NAME,
                    status="success",
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
                    job_name=DATA_RETENTION_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
