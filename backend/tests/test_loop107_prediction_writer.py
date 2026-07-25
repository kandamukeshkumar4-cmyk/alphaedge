"""Loop107 — the production writer for ``prediction_logs``.

``PredictionLog`` had eight API readers and NO production writer, so
``/api/v1/opportunities`` reported ``with_model_p=0`` in prod. These tests pin
the writer's contract: it persists forward-only predictions for OPEN markets
from the EXISTING prediction path, is idempotent inside its recency window,
skips markets that are resolved or already locked out, and never records a
field that was not knowable at prediction time.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    Market,
    MarketStatus,
    OddsSnapshot,
    OrderOutcome,
    PredictionLog,
)
from app.services.prediction_writer import (
    prediction_writer_task,
    write_model_predictions,
)


async def _market(
    db_session,
    slug: str,
    *,
    status: MarketStatus = MarketStatus.OPEN,
    volume: int = 1000,
    yes_price: float | None = 0.55,
    lock_at: datetime | None = None,
    winning_outcome: OrderOutcome | None = None,
    resolved_at: datetime | None = None,
) -> Market:
    market = Market(
        slug=slug,
        title=f"Market {slug}",
        question="?",
        status=status,
        volume=volume,
        lock_at=lock_at,
        winning_outcome=winning_outcome,
        resolved_at=resolved_at,
    )
    db_session.add(market)
    await db_session.flush()
    if yes_price is not None:
        db_session.add(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=Decimal(str(yes_price)),
                source="seed",
                captured_at=datetime.now(UTC) - timedelta(minutes=2),
            )
        )
        await db_session.flush()
    return market


async def _rows(db_session, slug: str) -> list[PredictionLog]:
    result = await db_session.execute(
        select(PredictionLog).where(PredictionLog.market_slug == slug)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_writer_persists_predictions_for_open_markets(db_session):
    await _market(db_session, "open-a", volume=5000, yes_price=0.60)
    await _market(db_session, "open-b", volume=4000, yes_price=0.40)
    # No market-implied price at all → skipped honestly, never invented.
    await _market(db_session, "open-no-price", volume=3000, yes_price=None)

    summary = await write_model_predictions(db_session)

    assert summary["written"] == 2
    assert summary["skipped_no_market_price"] == 1
    assert summary["errors"] == 0

    rows_a = await _rows(db_session, "open-a")
    assert len(rows_a) == 1
    row = rows_a[0]
    assert 0.0 <= float(row.predicted_prob) <= 1.0
    # The row is linked to the exact odds snapshot that fed the prediction.
    assert row.odds_snapshot_id is not None
    assert row.market_id is not None
    assert row.explanation["writer"] == "prediction_writer"
    assert row.explanation["market_implied"] == 0.60
    # The reused prediction path stamps the PRODUCING code path, never a
    # model that did not run.
    assert row.explanation["producer"] is not None

    assert len(await _rows(db_session, "open-b")) == 1
    assert await _rows(db_session, "open-no-price") == []


@pytest.mark.asyncio
async def test_writer_is_idempotent_within_window(db_session):
    await _market(db_session, "idem", volume=5000, yes_price=0.60)

    first = await write_model_predictions(db_session, window_sec=1800)
    second = await write_model_predictions(db_session, window_sec=1800)

    assert first["written"] == 1
    assert second["written"] == 0
    assert second["skipped_recent"] == 1
    assert len(await _rows(db_session, "idem")) == 1

    # Once the window has elapsed the writer records a NEW belief (append-only
    # history the edge_history reader consumes) rather than mutating the old one.
    later = await write_model_predictions(
        db_session, now=datetime.now(UTC) + timedelta(hours=2), window_sec=1800
    )
    assert later["written"] == 1
    assert len(await _rows(db_session, "idem")) == 2


@pytest.mark.asyncio
async def test_writer_skips_resolved_and_locked_out_markets(db_session):
    now = datetime.now(UTC)
    await _market(
        db_session,
        "resolved",
        status=MarketStatus.RESOLVED,
        volume=9000,
        winning_outcome=OrderOutcome.YES,
        resolved_at=now - timedelta(hours=1),
    )
    await _market(
        db_session,
        "locked-out",
        volume=8000,
        lock_at=now - timedelta(minutes=5),
    )
    await _market(db_session, "still-open", volume=7000, lock_at=now + timedelta(hours=3))

    summary = await write_model_predictions(db_session, now=now)

    # A resolved market never even enters the candidate set (known outcome).
    assert summary["candidates"] == 2
    assert summary["skipped_locked_out"] == 1
    assert summary["written"] == 1
    assert await _rows(db_session, "resolved") == []
    assert await _rows(db_session, "locked-out") == []
    assert len(await _rows(db_session, "still-open")) == 1


@pytest.mark.asyncio
async def test_writer_never_writes_lookahead_fields(db_session):
    """A row may contain only what was knowable at prediction time."""
    now = datetime.now(UTC)
    market = await _market(
        db_session,
        "no-leak",
        volume=5000,
        yes_price=0.35,
        lock_at=now + timedelta(hours=6),
    )
    # Resolution data EXISTS on the row (a market can be graded later); the
    # writer must not read or copy any of it.
    market.winning_outcome = OrderOutcome.YES
    market.resolved_at = now + timedelta(days=1)
    await db_session.flush()

    await write_model_predictions(db_session, now=now)

    row = (await _rows(db_session, "no-leak"))[0]
    # predicted_at is the pass time — never stamped into the future.
    predicted_at = row.predicted_at
    if predicted_at.tzinfo is None:
        predicted_at = predicted_at.replace(tzinfo=UTC)
    assert predicted_at <= datetime.now(UTC)
    # lock_at is the SCHEDULED close (knowable now), not the resolution time.
    def _utc(value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    assert row.lock_at is not None
    assert _utc(row.lock_at) == _utc(market.lock_at)
    assert _utc(row.lock_at) < _utc(market.resolved_at)

    banned = {
        "outcome",
        "winning_outcome",
        "actual_outcome",
        "resolved",
        "resolved_at",
        "resolution",
        "closing_implied",
        "brier",
        "pnl",
    }
    assert banned.isdisjoint(row.explanation.keys())
    # And no resolution value leaked in under another key name.
    assert "YES" not in {str(v) for v in row.explanation.values()}


@pytest.mark.asyncio
async def test_dual_wiring_cannot_double_insert_same_window(engine):
    """AUDIT107 fix 1: the two wirings are single-flight.

    The writer is dual-wired — an in-process wall-clock loop AND an ARQ cron —
    and in production both live in the same uvicorn process. The recency check
    is check-then-write, so overlapping passes could each see an empty window
    and insert. Drive BOTH entry points concurrently and assert the window
    still holds exactly one row.
    """
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as setup:
        await _market(setup, "dual-wired", volume=5000, yes_price=0.60)
        await setup.commit()

    # Both entry points are prediction_writer_task: the ARQ cron calls it and
    # so does _prediction_writer_loop (boot catch-up + every pass).
    results = await asyncio.gather(
        prediction_writer_task({"session_factory": factory}),
        prediction_writer_task({"session_factory": factory}),
    )

    async with factory() as check:
        rows = (
            (
                await check.execute(
                    select(PredictionLog).where(
                        PredictionLog.market_slug == "dual-wired"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    # One pass wrote it; the other honestly reported the row as already recent.
    assert sorted(result["written"] for result in results) == [0, 1]
    assert sum(result["skipped_recent"] for result in results) == 1
