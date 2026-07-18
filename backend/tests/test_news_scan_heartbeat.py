"""Loop V70: news_scan heartbeat surfaces skipped-reason like whale/venue loops."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.observability import loop_state
from app.workers import tasks as worker_tasks


@pytest.fixture(autouse=True)
def _reset_heartbeats():
    loop_state.reset()
    yield
    loop_state.reset()


@pytest.mark.asyncio
async def test_news_scan_task_skipped_reason_for_heartbeat_detail():
    result = await worker_tasks.news_scan_task(
        {"settings": SimpleNamespace(news_signals_enabled=False)}
    )
    assert result["skipped"] is True
    assert "NEWS_SIGNALS_ENABLED" in result["reason"]
    # Same detail shape as whale_flow / venue_gap loops in main.py.
    detail = f"skipped:{result.get('reason')}"
    loop_state.record_heartbeat("news_scan", detail=detail)
    snap = loop_state.snapshot()["news_scan"]
    assert snap["detail"] == "skipped:NEWS_SIGNALS_ENABLED=false"
    assert snap["status"] == "ok"


@pytest.mark.asyncio
async def test_news_scan_loop_records_skipped_detail(monkeypatch):
    """Drive one pass of _news_scan_loop via monkeypatched sleep + task."""
    import app.main as main_mod

    calls: list[tuple] = []

    async def fake_sleep(_sec):
        # Stop after first sleep → first task pass.
        raise _StopLoop()

    class _StopLoop(Exception):
        pass

    async def fake_task(_ctx):
        return {"skipped": True, "reason": "NEWS_SIGNALS_ENABLED=false"}

    def capture_hb(name, *, status="ok", detail=None, duration_ms=None):
        calls.append((name, status, detail))

    monkeypatch.setattr(main_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(worker_tasks, "news_scan_task", fake_task)
    # Re-bind the import used inside the loop body via workers.tasks path:
    # the loop does `from app.workers.tasks import news_scan_task` each pass,
    # so patch the module attribute before the import resolves.
    monkeypatch.setattr("app.workers.tasks.news_scan_task", fake_task)
    monkeypatch.setattr(main_mod, "record_heartbeat", capture_hb)

    with pytest.raises(_StopLoop):
        await main_mod._news_scan_loop()

    # Loop sleeps first, then runs task — StopLoop on first sleep means zero
    # heartbeats. Re-run with sleep that allows one iteration.
    n = {"i": 0}

    async def sleep_once(_sec):
        n["i"] += 1
        if n["i"] > 1:
            raise _StopLoop()

    monkeypatch.setattr(main_mod.asyncio, "sleep", sleep_once)
    calls.clear()
    with pytest.raises(_StopLoop):
        await main_mod._news_scan_loop()

    assert ("news_scan", "ok", "skipped:NEWS_SIGNALS_ENABLED=false") in calls


@pytest.mark.asyncio
async def test_news_scan_loop_records_scanned_count(monkeypatch):
    import app.main as main_mod

    calls: list[tuple] = []
    n = {"i": 0}

    class _StopLoop(Exception):
        pass

    async def sleep_once(_sec):
        n["i"] += 1
        if n["i"] > 1:
            raise _StopLoop()

    async def fake_task(_ctx):
        return {"scanned": 3, "results": {"a": "ok"}}

    def capture_hb(name, *, status="ok", detail=None, duration_ms=None):
        calls.append((name, status, detail))

    monkeypatch.setattr(main_mod.asyncio, "sleep", sleep_once)
    monkeypatch.setattr("app.workers.tasks.news_scan_task", fake_task)
    monkeypatch.setattr(main_mod, "record_heartbeat", capture_hb)

    with pytest.raises(_StopLoop):
        await main_mod._news_scan_loop()

    assert ("news_scan", "ok", "scanned=3") in calls
