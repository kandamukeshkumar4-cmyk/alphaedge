"""Loop V76 F2 — heartbeat semantics behind the prod "never" observation.

Prod anomaly investigated: ``forecast_autolock`` / ``external_resolve`` showed
``status="never"`` on ``GET /api/v1/system/loops``. Live prod verification
(2026-07-20) shows both ``status=ok`` with fresh heartbeats and 36 scored
autolock forecasts — the loops run. These tests pin the exact semantics that
explain a transient "never" without touching the code under test:

1. A loop with no recorded pass maps to ``running=False, status="never"``;
   heartbeats are in-process memory, so every (re)boot starts at "never".
2. The first pass happens only AFTER the loop's initial sleep, so a freshly
   booted process legitimately reads "never" for one interval.
3. ``_paced_sleep`` stretches the cadence to the idle interval when no client
   is active (COST-01/02), so an idle boot can show "never" for up to ~1h.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.api.v1.system import get_loops
from app.main import _paced_sleep
from app.observability import loop_state
from app.observability.loop_state import LOOP_INTERVALS, record_heartbeat


@pytest.fixture(autouse=True)
def _clean_heartbeats():
    loop_state.reset()
    try:
        yield
    finally:
        loop_state.reset()


def _loop_row(loops: dict, name: str) -> dict:
    return next(row for row in loops["loops"] if row["name"] == name)


@pytest.mark.asyncio
async def test_never_until_first_pass_then_ok():
    """The endpoint mapping that produced the prod observation, verbatim."""
    loops = await get_loops()
    for name in ("forecast_autolock", "external_resolve", "external_market_bridge"):
        row = _loop_row(loops, name)
        assert row["running"] is False
        assert row["status"] == "never"
        assert row["last_heartbeat"] is None
        # Displayed cadence matches the fast interval used in main.py sleeps.
        assert row["interval_sec"] == 900

    record_heartbeat("forecast_autolock", detail="eligible=4")
    loops = await get_loops()
    row = _loop_row(loops, "forecast_autolock")
    assert row["running"] is True
    assert row["status"] == "ok"
    assert row["last_heartbeat"] is not None
    assert row["detail"] == "eligible=4"
    # A sibling loop is unaffected: "never" is per-loop, not global.
    assert _loop_row(loops, "external_resolve")["status"] == "never"


@pytest.mark.asyncio
async def test_error_status_still_counts_as_running():
    """Alive-but-failing is visible, never hidden as a dead loop."""
    record_heartbeat("external_resolve", status="error", detail="pass failed")
    row = _loop_row(await get_loops(), "external_resolve")
    assert row["running"] is True
    assert row["status"] == "error"
    assert row["detail"] == "pass failed"


def test_loop_intervals_cover_the_three_external_chain_loops():
    """The displayed cadence exists and matches the main.py fast sleep."""
    assert LOOP_INTERVALS["forecast_autolock"] == 900
    assert LOOP_INTERVALS["external_resolve"] == 900
    assert LOOP_INTERVALS["external_market_bridge"] == 900


@pytest.mark.asyncio
async def test_paced_sleep_stretches_to_idle_interval_without_demand(monkeypatch):
    """COST-01/02: no active client -> cadence stretches toward the idle
    interval; this is why an idle prod boot shows "never" past 15 min."""
    monkeypatch.setattr("app.main._live_tick_demand", lambda: False)
    started = time.monotonic()
    await _paced_sleep(0.05, 0.22)
    elapsed = time.monotonic() - started
    # fast=0.05 chunks until slept >= idle=0.22 -> ~0.25, and never less.
    assert elapsed >= 0.22


@pytest.mark.asyncio
async def test_paced_sleep_wakes_after_one_fast_chunk_on_demand(monkeypatch):
    monkeypatch.setattr("app.main._live_tick_demand", lambda: True)
    started = time.monotonic()
    await _paced_sleep(0.05, 60.0)
    elapsed = time.monotonic() - started
    assert elapsed < 1.0  # returned after the first 0.05 chunk, not the idle 60s


@pytest.mark.asyncio
async def test_paced_sleep_idle_never_below_fast(monkeypatch):
    """The clamp: idle_sec < fast_sec collapses to a single fast chunk."""
    monkeypatch.setattr("app.main._live_tick_demand", lambda: False)
    started = time.monotonic()
    await _paced_sleep(0.10, 0.01)
    elapsed = time.monotonic() - started
    assert 0.10 <= elapsed < 1.0


@pytest.mark.asyncio
async def test_first_pass_only_after_initial_sleep_documents_boot_grace():
    """The boot-grace window itself: a loop that sleeps before its first pass
    leaves the registry empty ("never") for the whole first interval."""
    async def _mini_loop() -> None:
        while True:
            await asyncio.sleep(0.2)  # the initial sleep, as in main.py loops
            record_heartbeat("external_resolve")

    task = asyncio.create_task(_mini_loop())
    try:
        await asyncio.sleep(0.05)  # mid-first-interval: still "never"
        assert _loop_row(await get_loops(), "external_resolve")["status"] == "never"
        await asyncio.sleep(0.25)  # past the first pass
        assert _loop_row(await get_loops(), "external_resolve")["status"] == "ok"
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
