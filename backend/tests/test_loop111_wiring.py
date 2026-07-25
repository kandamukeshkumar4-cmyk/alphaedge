"""Loop111 — wire the three dead-writer / blind-spot defects found by NOWRITER-SWEEP.md.

All three are the same disease: production code that exists, is tested in
isolation, and is never actually invoked (or never actually observed).

* Fix A (sweep finding 1, ``NOWRITER-SWEEP.md`` §2 row 1):
  ``VenueMatchService.match_open_catalog()`` had zero production callers, so
  ``venue_market_matches`` was permanently empty and ``venue_gap_task`` refreshed
  gaps over nothing. It now runs at the head of ``venue_gap_task``.
* Fix B (sweep finding 2 / §3 AT-RISK #1): ``snapshot_whale_positions_task`` was
  an ARQ ``cron()`` with no in-process mirror in ``app/main.py``; prod runs
  uvicorn only, so ``wallet_position_snapshots`` had no production writer.
* Fix C (sweep §3b): ``GET /api/v1/system/loops`` iterated a hardcoded tuple that
  had drifted behind the loop registry, hiding six live loops.

Paper-trading simulation only: no order-path imports, no LLM calls, no secrets.
"""
from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Market, MarketStatus, VenueMarketMatch


# ---------------------------------------------------------------------------
# Fix A — venue matching is actually invoked by the venue gap loop
# ---------------------------------------------------------------------------


def _market(*, slug: str, source: str, title: str, external_id: str, lock_at: datetime) -> Market:
    return Market(
        slug=slug,
        title=title,
        question=title,
        source=source,
        external_id=external_id,
        status=MarketStatus.OPEN,
        lock_at=lock_at,
    )


def _point_session_local_at(monkeypatch, engine) -> None:
    """``venue_gap_task`` opens its own ``AsyncSessionLocal``; aim it at the test DB."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", factory)


@pytest.mark.asyncio
async def test_venue_gap_task_invokes_matcher_and_persists_matches(
    monkeypatch, engine, db_session
):
    """The gap loop must feed itself: matcher first, then gap refresh.

    Before Loop111 the matcher had zero callers (NOWRITER-SWEEP.md §1a,
    ``venue_match_service.py:141`` writer unreachable) so this table stayed
    empty forever and prod reported ``venue_gap ... upserted=0``.
    """
    from app.workers.tasks import venue_gap_task

    lock_at = datetime.now(UTC) + timedelta(days=2)
    # Same event id + same title + same close time => confidence 1.0, well
    # above the matcher's 0.75 gate.
    db_session.add(
        _market(
            slug="pm-lakers-celtics-2026",
            source="polymarket",
            title="Lakers beat Celtics on 2026-01-15",
            external_id="evt-lal-bos-2026-01-15",
            lock_at=lock_at,
        )
    )
    db_session.add(
        _market(
            slug="ks-lakers-celtics-2026",
            source="kalshi",
            title="Lakers beat Celtics on 2026-01-15",
            external_id="evt-lal-bos-2026-01-15",
            lock_at=lock_at,
        )
    )
    await db_session.commit()

    _point_session_local_at(monkeypatch, engine)

    summary = await venue_gap_task({})

    assert summary["matched"] == 1, f"matcher did not run or matched nothing: {summary}"

    stored = list((await db_session.scalars(select(VenueMarketMatch))).all())
    assert len(stored) == 1
    assert stored[0].pm_slug == "pm-lakers-celtics-2026"
    assert stored[0].ks_slug == "ks-lakers-celtics-2026"
    assert stored[0].confidence >= 0.75

    # Idempotent: a second pass updates the same (pm_slug, ks_slug) row rather
    # than inserting a duplicate — the 60s loop must not grow the table.
    second = await venue_gap_task({})
    assert second["matched"] == 1
    await db_session.rollback()  # drop the stale identity map read above
    again = list((await db_session.scalars(select(VenueMarketMatch))).all())
    assert len(again) == 1


@pytest.mark.asyncio
async def test_venue_gap_task_survives_empty_match_result(monkeypatch, engine, db_session):
    """No matchable catalog must still be a successful pass, not an exception.

    An empty catalog is the *normal* state on a cold DB; if that raised, the
    whole venue_gap loop would flip to status=error and the gap refresh that
    still has work to do would never run.
    """
    from app.workers.tasks import venue_gap_task

    _point_session_local_at(monkeypatch, engine)

    summary = await venue_gap_task({})

    assert summary["matched"] == 0
    # The gap refresh still ran and reported honestly.
    assert summary["matches"] == 0
    assert summary["upserted"] == 0
    assert not summary.get("skipped")
    assert list((await db_session.scalars(select(VenueMarketMatch))).all()) == []


@pytest.mark.asyncio
async def test_venue_gap_task_survives_matcher_failure(monkeypatch, engine):
    """A matcher blow-up is isolated: the gap refresh still completes."""
    from app.workers.tasks import venue_gap_task

    _point_session_local_at(monkeypatch, engine)

    async def _boom(self, **kwargs):
        raise RuntimeError("upstream catalog exploded")

    monkeypatch.setattr(
        "app.services.venue_match_service.VenueMatchService.match_open_catalog", _boom
    )

    summary = await venue_gap_task({})
    assert summary["matched"] is None  # matching failed, honestly reported
    assert summary["upserted"] == 0  # gap refresh still ran


def test_venue_gap_task_bounds_the_match_pass():
    """Matching runs every 60s, so it must be bounded, not a full O(n*m) sweep."""
    import app.workers.tasks as tasks_mod

    src = inspect.getsource(tasks_mod.venue_gap_task)
    assert "venue_gap_match_limit" in src
    assert "catalog_limit=match_limit" in src
    assert "max_pairs=match_limit" in src


# ---------------------------------------------------------------------------
# Fix B — the whale position snapshot loop is dual-wired in main.py
# ---------------------------------------------------------------------------


class _FakeSession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _fake_session_local():
    class _Ctx:
        async def __aenter__(self):
            return _FakeSession()

        async def __aexit__(self, *exc):
            return False

    return _Ctx()


class _FakeMarketService:
    def __init__(self, session):
        pass

    async def seed_system_account(self, *args, **kwargs):
        return None

    async def seed_catalog_markets(self):
        return None


@pytest.mark.asyncio
async def test_whale_snapshot_loop_registered_and_wallclock(monkeypatch):
    """``snapshot_whale_positions_task`` must run in-process on a wall clock.

    NOWRITER-SWEEP.md §3 AT-RISK #1: it was a ``cron()`` job only, and prod runs
    uvicorn with no ARQ worker, so ``wallet_position_snapshots`` never got a row
    (``/api/v1/smart-money`` → ``wallet_count: 0``). Mirrors the
    ``_prediction_writer_loop`` precedent: boot catch-up first, never sleep-first.
    """
    import app.main as main_mod
    from app.main import _whale_positions_loop, lifespan
    from app.observability.loop_state import LOOP_INTERVALS

    # --- the loop exists, is on the registry, and is wall-clock paced --------
    assert "whale_positions" in LOOP_INTERVALS
    src = inspect.getsource(_whale_positions_loop)
    assert "_paced_sleep" in src, "loop must use the shared wall-clock pacer"
    assert "snapshot_whale_positions_task" in src

    # Never sleep-first: the boot catch-up call must precede the `while True`.
    body = src.split('"""', 2)[-1]
    first_call = body.index("snapshot_whale_positions_task({})")
    assert first_call < body.index("while True"), "loop sleeps before its first pass"

    # Single-flight by construction: one sequential task, no concurrent fan-out.
    assert "asyncio.gather" not in src and "create_task" not in src

    # --- and the lifespan actually registers it -----------------------------
    monkeypatch.setattr(main_mod, "AsyncSessionLocal", _fake_session_local)
    monkeypatch.setattr(main_mod, "MarketService", _FakeMarketService)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.services.signal_event_seed.seed_signal_events", _noop)
    monkeypatch.setattr("app.services.skill_seed_service.seed_default_skills", _noop)
    monkeypatch.setattr("app.services.scanner_seed_service.seed_starter_scanners", _noop)
    monkeypatch.setattr("app.data.streams.runner.background_loop_plan", lambda s: {})
    monkeypatch.setattr(main_mod.settings, "live_feed_enabled", False)
    monkeypatch.setattr("app.workers.tasks.snapshot_whale_positions_task", _noop)

    created_names: list[str] = []
    created_tasks: list[asyncio.Task] = []
    real_create_task = asyncio.create_task

    def spy_create_task(coro, *args, **kwargs):
        code = getattr(coro, "cr_code", None)
        if code is not None:
            created_names.append(code.co_name)
        task = real_create_task(coro, *args, **kwargs)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(main_mod.asyncio, "create_task", spy_create_task)

    class _DummyApp:
        pass

    try:
        async with lifespan(_DummyApp()):
            assert "_whale_positions_loop" in created_names, (
                f"whale positions loop not registered (saw {sorted(created_names)})"
            )
    finally:
        for task in created_tasks:
            task.cancel()
        await asyncio.gather(*created_tasks, return_exceptions=True)


def test_whale_snapshot_task_is_bounded_per_pass():
    """One upstream HTTP call per wallet every ~3 min — must be capped."""
    import app.workers.tasks as tasks_mod

    assert tasks_mod.WHALE_POSITION_WALLET_LIMIT > 0
    src = inspect.getsource(tasks_mod.snapshot_whale_positions_task)
    assert ".limit(limit)" in src


def test_whale_positions_loop_is_flag_gated():
    """Every in-process mirror is individually killable (precedent: all 20 siblings)."""
    from app.core.config import get_settings

    settings = get_settings()
    assert hasattr(settings, "scheduler_whale_positions_enabled")
    assert hasattr(settings, "whale_positions_interval_sec")


# ---------------------------------------------------------------------------
# Fix C — /api/v1/system/loops is derived from the registry, not hardcoded
# ---------------------------------------------------------------------------


def test_system_loops_covers_all_registered_loops():
    """The observability endpoint must not be able to drift behind the registry.

    NOWRITER-SWEEP.md §3b: the hardcoded ``_ALL_LOOPS`` tuple omitted
    ``prediction_writer`` — the loop feeding twelve ``PredictionLog`` readers —
    which is precisely the blind spot that let dead-writer bugs survive in prod.
    """
    from app.api.v1.system import _ALL_LOOPS, _all_loops
    from app.observability.loop_state import LOOP_INTERVALS

    assert "prediction_writer" in _ALL_LOOPS
    assert len(_ALL_LOOPS) >= len(LOOP_INTERVALS)
    assert set(LOOP_INTERVALS).issubset(set(_ALL_LOOPS))

    # Loops the sweep flagged as invisible are now covered (either registered
    # or surfaced the moment they beat).
    for name in ("prediction_writer", "scanner_scheduler", "whale_positions"):
        assert name in _ALL_LOOPS, name

    # A live loop that is not in the registry is surfaced, never dropped.
    derived = _all_loops({"totally_new_loop": {"status": "ok"}})
    assert "totally_new_loop" in derived
    assert len(derived) == len(_ALL_LOOPS) + 1

    # And it never invents a loop that neither registry nor heartbeat knows.
    assert set(_all_loops({})) == set(_ALL_LOOPS)


@pytest.mark.asyncio
async def test_system_loops_endpoint_reports_the_derived_list():
    """End-to-end: the public GET reflects the derived list, honestly."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.observability.loop_state import LOOP_INTERVALS

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")

    assert response.status_code == 200
    payload = response.json()
    names = [row["name"] for row in payload["loops"]]
    assert "prediction_writer" in names
    assert "whale_positions" in names
    assert len(names) >= len(LOOP_INTERVALS)
    assert payload["paper_trading_only"] is True
    # A loop that has never run stays honest — no fabricated heartbeat.
    for row in payload["loops"]:
        if row["last_heartbeat"] is None:
            assert row["status"] == "never"
            assert row["running"] is False
