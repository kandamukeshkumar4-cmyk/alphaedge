"""Task 1 — in-process scheduler registration test.

The deployed free tier has no ARQ worker (REDIS_URL=redis://disabled), so the
periodic worker tasks defined in ``app/workers/tasks.py`` must run in-process
inside the API. This test asserts that every NEW background loop
(news_scan, weather_scan, morning_research, whale refresh, wc2026 resolve) is
registered via ``asyncio.create_task`` when the app starts — i.e. when the
``lifespan`` async context manager is entered.

Pattern: invoke the real ``lifespan`` directly (the repo has no existing test
that drives the real lifespan via TestClient because ``AsyncSessionLocal``
points at postgres), with the DB-touching and network startup work stubbed out,
and spy on ``asyncio.create_task`` to capture the registered coroutine names.
"""
from __future__ import annotations

import asyncio

import pytest


# The new in-process loops added in Task 1. price-ingest/tick/eval already
# existed and are not the subject of this test.
EXPECTED_NEW_LOOPS = {
    "_news_scan_loop",
    "_news_mispricing_loop",
    "_unusual_flow_loop",
    "_weather_scan_loop",
    "_morning_research_loop",
    "_whale_refresh_loop",
    "_wc2026_resolve_loop",
    "_forecast_autolock_loop",
    "_drift_detect_loop",
    "_ops_alerts_loop",
    "_portfolio_equity_loop",
    "_daily_digest_loop",
    "_jobrun_retention_loop",
}


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
async def test_inprocess_scheduler_registers_all_new_background_tasks(monkeypatch):
    """On startup the lifespan must schedule every gated new background loop."""
    import app.main as main_mod
    from app.main import lifespan

    # Stub the DB session + heavy startup work so lifespan runs with no
    # postgres and no network. The new loops sleep first, so they never fire
    # during this test; stubbing the worker tasks is belt-and-braces.
    monkeypatch.setattr(main_mod, "AsyncSessionLocal", _fake_session_local)
    monkeypatch.setattr(main_mod, "MarketService", _FakeMarketService)

    async def _noop(*args, **kwargs):
        return None

    # REL-COLD-DB added warmup_db() before seeding; stub it too or the test
    # hits real localhost Postgres and ConnectionRefusedError (no Docker).
    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.services.signal_event_seed.seed_signal_events", _noop)
    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.data.streams.runner.background_loop_plan", lambda s: {})
    # Skip the live-ingest block (network) — the new loops live outside it.
    monkeypatch.setattr(main_mod.settings, "live_feed_enabled", False)

    for fn_name in (
        "news_scan_task",
        "news_mispricing_scan_task",
        "unusual_flow_scan_task",
        "weather_scan_task",
        "morning_research_task",
        "refresh_whales_task",
        "wc2026_resolve_task",
    ):
        monkeypatch.setattr(f"app.workers.tasks.{fn_name}", _noop)

    # Spy on asyncio.create_task to record which coroutines get scheduled.
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
            registered = set(created_names)
            missing = EXPECTED_NEW_LOOPS - registered
            assert not missing, (
                f"In-process scheduler did not register: {missing} "
                f"(saw {sorted(registered)})"
            )
    finally:
        for task in created_tasks:
            task.cancel()
        await asyncio.gather(*created_tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_inprocess_scheduler_respects_disabled_flags(monkeypatch):
    """When a flag is False, that loop must NOT be registered."""
    import app.main as main_mod
    from app.main import lifespan

    monkeypatch.setattr(main_mod, "AsyncSessionLocal", _fake_session_local)
    monkeypatch.setattr(main_mod, "MarketService", _FakeMarketService)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.services.signal_event_seed.seed_signal_events", _noop)
    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.data.streams.runner.background_loop_plan", lambda s: {})
    monkeypatch.setattr(main_mod.settings, "live_feed_enabled", False)

    for fn_name in (
        "news_scan_task",
        "news_mispricing_scan_task",
        "unusual_flow_scan_task",
        "weather_scan_task",
        "morning_research_task",
        "refresh_whales_task",
        "wc2026_resolve_task",
    ):
        monkeypatch.setattr(f"app.workers.tasks.{fn_name}", _noop)

    # Disable three of the new loops.
    monkeypatch.setattr(main_mod.settings, "scheduler_news_scan_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_news_mispricing_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_weather_scan_enabled", False)
    # The other three stay default-True.
    monkeypatch.setattr(main_mod.settings, "scheduler_morning_research_enabled", True)
    monkeypatch.setattr(main_mod.settings, "scheduler_whale_refresh_enabled", True)
    monkeypatch.setattr(main_mod.settings, "scheduler_wc2026_resolve_enabled", True)

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
            registered = set(created_names)
            assert "_news_scan_loop" not in registered, (
                "news scan loop registered despite SCHEDULER_NEWS_SCAN_ENABLED=False"
            )
            assert "_news_mispricing_loop" not in registered, (
                "news mispricing loop registered despite "
                "SCHEDULER_NEWS_MISPRICING_ENABLED=False"
            )
            assert "_weather_scan_loop" not in registered, (
                "weather scan loop registered despite "
                "SCHEDULER_WEATHER_SCAN_ENABLED=False"
            )
            assert {
                "_morning_research_loop",
                "_whale_refresh_loop",
                "_wc2026_resolve_loop",
            }.issubset(registered), (
                f"Enabled loops missing from {sorted(registered)}"
            )
    finally:
        for task in created_tasks:
            task.cancel()
        await asyncio.gather(*created_tasks, return_exceptions=True)
