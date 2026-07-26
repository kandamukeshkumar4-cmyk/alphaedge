"""Loop112 — dual-wire remaining AT-RISK cron-only writers + retrain boot catch-up.

NOWRITER-SWEEP.md §3: ARQ ``cron()`` jobs with no in-process mirror never run in
prod (uvicorn only). ``snapshot_whale_positions`` was dual-wired in Loop111;
this loop covers the rest that are safe to run, fixes sleep-first on
``refresh_whales`` / ``generic_artifact_retrain``, and records SKIPs for
obsolete or dangerous tasks.

Paper-trading simulation only: no LLM calls, no secrets, no migrations.
"""
from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models import ModelVersion
from app.forecasting.generic_artifact import MODEL_NAME
from app.observability.loop_state import LOOP_INTERVALS, reset as reset_heartbeats


# ---------------------------------------------------------------------------
# Shared lifespan spies (mirror test_loop111_wiring)
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


async def _noop(*args, **kwargs):
    return None


def _assert_boot_catchup_before_while(src: str, task_token: str) -> None:
    """Boot catch-up call must precede ``while True`` (never sleep-first)."""
    body = src.split('"""', 2)[-1]
    first_call = body.index(task_token)
    assert first_call < body.index("while True"), "loop sleeps before its first pass"
    assert "_paced_sleep" in src, "loop must use the shared wall-clock pacer"
    assert "asyncio.gather" not in src and "create_task" not in src


async def _assert_loop_registered(
    monkeypatch,
    *,
    loop_fn,
    loop_name: str,
    interval_key: str,
    task_token: str,
    flag_attr: str,
    mock_targets: list[str],
) -> None:
    import app.main as main_mod
    from app.main import lifespan

    assert interval_key in LOOP_INTERVALS
    src = inspect.getsource(loop_fn)
    _assert_boot_catchup_before_while(src, task_token)

    monkeypatch.setattr(main_mod, "AsyncSessionLocal", _fake_session_local)
    monkeypatch.setattr(main_mod, "MarketService", _FakeMarketService)
    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.services.signal_event_seed.seed_signal_events", _noop)
    monkeypatch.setattr("app.services.skill_seed_service.seed_default_skills", _noop)
    monkeypatch.setattr("app.services.scanner_seed_service.seed_starter_scanners", _noop)
    monkeypatch.setattr("app.data.streams.runner.background_loop_plan", lambda s: {})
    monkeypatch.setattr(main_mod.settings, "live_feed_enabled", False)
    monkeypatch.setattr(main_mod.settings, flag_attr, True)
    for target in mock_targets:
        monkeypatch.setattr(target, _noop)

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
            assert loop_name in created_names, (
                f"{loop_name} not registered (saw {sorted(created_names)})"
            )
    finally:
        for task in created_tasks:
            task.cancel()
        await asyncio.gather(*created_tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# P1 — whale refresh boot catch-up (was sleep-first → status=never)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whale_refresh_loop_registered_and_wallclock(monkeypatch):
    """``refresh_whales_task`` must boot-catch-up; sleep-first starved TrackedWallet."""
    from app.main import _whale_refresh_loop

    await _assert_loop_registered(
        monkeypatch,
        loop_fn=_whale_refresh_loop,
        loop_name="_whale_refresh_loop",
        interval_key="whale_refresh",
        task_token="refresh_whales_task({})",
        flag_attr="scheduler_whale_refresh_enabled",
        mock_targets=["app.workers.tasks.refresh_whales_task"],
    )


# ---------------------------------------------------------------------------
# AT-RISK #2 — model_retrain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_retrain_loop_registered_and_wallclock(monkeypatch):
    from app.core.config import get_settings
    from app.main import _model_retrain_loop

    settings = get_settings()
    assert hasattr(settings, "scheduler_model_retrain_enabled")

    await _assert_loop_registered(
        monkeypatch,
        loop_fn=_model_retrain_loop,
        loop_name="_model_retrain_loop",
        interval_key="model_retrain",
        task_token="model_retrain_task({})",
        flag_attr="scheduler_model_retrain_enabled",
        mock_targets=["app.workers.model_retrain.model_retrain_task"],
    )


# ---------------------------------------------------------------------------
# AT-RISK #3 — nightly_backtest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nightly_backtest_loop_registered_and_wallclock(monkeypatch):
    from app.core.config import get_settings
    from app.main import _nightly_backtest_loop

    settings = get_settings()
    assert hasattr(settings, "scheduler_nightly_backtest_enabled")

    await _assert_loop_registered(
        monkeypatch,
        loop_fn=_nightly_backtest_loop,
        loop_name="_nightly_backtest_loop",
        interval_key="nightly_backtest",
        task_token="nightly_backtest_task({})",
        flag_attr="scheduler_nightly_backtest_enabled",
        mock_targets=["app.workers.tasks.nightly_backtest_task"],
    )


# ---------------------------------------------------------------------------
# AT-RISK #4 — capture_market_snapshots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_market_snapshots_loop_registered_and_wallclock(monkeypatch):
    from app.core.config import get_settings
    from app.main import _market_snapshots_loop

    settings = get_settings()
    assert hasattr(settings, "scheduler_market_snapshots_enabled")

    await _assert_loop_registered(
        monkeypatch,
        loop_fn=_market_snapshots_loop,
        loop_name="_market_snapshots_loop",
        interval_key="market_snapshots",
        task_token="capture_market_snapshots_task({})",
        flag_attr="scheduler_market_snapshots_enabled",
        mock_targets=["app.workers.tasks.capture_market_snapshots_task"],
    )


# ---------------------------------------------------------------------------
# AT-RISK #6 — order_expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_order_expiry_loop_registered_and_wallclock(monkeypatch):
    from app.core.config import get_settings
    from app.main import _order_expiry_loop

    settings = get_settings()
    assert hasattr(settings, "scheduler_order_expiry_enabled")

    await _assert_loop_registered(
        monkeypatch,
        loop_fn=_order_expiry_loop,
        loop_name="_order_expiry_loop",
        interval_key="order_expiry",
        task_token="order_expiry_task({})",
        flag_attr="scheduler_order_expiry_enabled",
        mock_targets=["app.workers.order_expiry.order_expiry_task"],
    )


# ---------------------------------------------------------------------------
# Retrain boot catch-up respects last-run (registry timestamps)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrain_boot_catchup_runs_once_and_respects_last_run(
    monkeypatch, engine, db_session
):
    """Boot catch-up runs when no week-window version; skips when one exists."""
    import app.main as main_mod
    from app.main import _generic_artifact_retrain_loop
    from app.observability import loop_state
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    reset_heartbeats()

    # Aim the registry check at the test DB (same pattern as venue_gap tests).
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", factory)

    # Empty registry → no week-window retrain yet.
    assert await main_mod._has_generic_artifact_retrain_this_week() is False

    calls: list[dict] = []

    async def _fake_task(ctx):
        calls.append(dict(ctx or {}))
        return {
            "skipped": False,
            "version": "test.boot.1",
            "row_count": 12,
            "activated": False,
        }

    monkeypatch.setattr(
        "app.workers.generic_artifact_retrain.generic_artifact_retrain_task",
        _fake_task,
    )

    async def _fast_sleep(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(main_mod, "_paced_sleep", _fast_sleep)

    # Seed a recent inactive registry row → has-check becomes True.
    db_session.add(
        ModelVersion(
            id=uuid4(),
            name=MODEL_NAME,
            version="test.week.1",
            artifact_path="/tmp/unused",
            training_data_hash="abc123",
            metrics={"brier": 0.2},
            is_active=False,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()
    assert await main_mod._has_generic_artifact_retrain_this_week() is True

    # Boot path with recent version must NOT call the task.
    calls.clear()
    reset_heartbeats()

    async def _has_true(*args, **kwargs):
        return True

    monkeypatch.setattr(main_mod, "_has_generic_artifact_retrain_this_week", _has_true)

    with pytest.raises(asyncio.CancelledError):
        await _generic_artifact_retrain_loop()

    assert calls == []
    beats = loop_state.snapshot()
    assert "generic_artifact_retrain" in beats
    assert beats["generic_artifact_retrain"]["detail"] == (
        "skipped:retrain_exists_this_week"
    )

    # Boot path with no recent version MUST call the task once before sleep.
    calls.clear()
    reset_heartbeats()

    async def _has_false(*args, **kwargs):
        return False

    monkeypatch.setattr(main_mod, "_has_generic_artifact_retrain_this_week", _has_false)

    with pytest.raises(asyncio.CancelledError):
        await _generic_artifact_retrain_loop()

    assert len(calls) == 1
    beats = loop_state.snapshot()
    assert beats["generic_artifact_retrain"]["status"] == "ok"
    assert "version=test.boot.1" in (beats["generic_artifact_retrain"]["detail"] or "")


def test_loop112_intervals_and_flags_present():
    from app.core.config import get_settings

    settings = get_settings()
    for key, expected in (
        ("whale_refresh", 604800),
        ("model_retrain", 86400),
        ("nightly_backtest", 86400),
        ("market_snapshots", 3600),
        ("order_expiry", 60),
        ("generic_artifact_retrain", 604800),
    ):
        assert LOOP_INTERVALS[key] == expected, key

    for attr in (
        "scheduler_whale_refresh_enabled",
        "scheduler_model_retrain_enabled",
        "scheduler_nightly_backtest_enabled",
        "scheduler_market_snapshots_enabled",
        "scheduler_order_expiry_enabled",
        "scheduler_generic_artifact_retrain_enabled",
    ):
        assert hasattr(settings, attr), attr


def test_loop112_skips_are_documented():
    """Obsolete / dangerous AT-RISK tasks must stay unwired (documented SKIP)."""
    import app.main as main_mod

    src = inspect.getsource(main_mod)
    # Historical closing is admin-POST only (not even an ARQ cron).
    assert "_historical_closing" not in src
    assert "capture_historical_closing_snapshots_task" not in src
    # Fixture ingest would pollute prod odds_snapshots.
    assert "ingest_odds_task" not in src or "ingest_odds" not in inspect.getsource(
        main_mod.lifespan
    )
    assert "_ingest_odds_loop" not in src
    # Cache-warm only; news_scan covers the DB writer; profile is compute-only.
    assert "_nightly_profile_refresh_loop" not in src
    assert "_fetch_news_signals_loop" not in src
