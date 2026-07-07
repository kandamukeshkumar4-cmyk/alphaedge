"""T01 finding #2 / T02 — degrade-to-polling: which background loops start.

Proves that disabling a WS stream does NOT remove the REST polling loops
(price_feed / live_ingest / live_tick), so the app degrades to polling.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.data.streams.base import ConnectionState, MarketStream
from app.data.streams.runner import background_loop_plan


def _settings(**kw):
    base = dict(
        live_feed_enabled=True,
        kalshi_ws_enabled=True,
        polymarket_ws_enabled=True,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_all_enabled_starts_streams_and_polling():
    plan = background_loop_plan(_settings())
    assert plan == ["price_feed", "live_ingest", "live_tick", "kalshi_ws", "polymarket_ws"]


def test_kalshi_ws_disabled_keeps_polling():
    plan = background_loop_plan(_settings(kalshi_ws_enabled=False))
    assert "kalshi_ws" not in plan
    # REST polling loops remain — degrade to polling.
    assert "live_tick" in plan
    assert "live_ingest" in plan
    assert "polymarket_ws" in plan


def test_both_ws_disabled_still_polls():
    plan = background_loop_plan(
        _settings(kalshi_ws_enabled=False, polymarket_ws_enabled=False)
    )
    assert plan == ["price_feed", "live_ingest", "live_tick"]


def test_live_feed_disabled_only_price_feed():
    plan = background_loop_plan(_settings(live_feed_enabled=False))
    assert plan == ["price_feed"]
    assert "kalshi_ws" not in plan and "polymarket_ws" not in plan


def test_config_defaults_enable_both_ws_streams():
    """With the shipped config defaults (WS on), the plan includes both streams.

    Reads the real field defaults from ``Settings`` so this fails if anyone flips
    ``kalshi_ws_enabled`` / ``polymarket_ws_enabled`` back to False.
    """
    from app.core.config import Settings

    fields = Settings.model_fields
    assert fields["live_feed_enabled"].default is True
    assert fields["kalshi_ws_enabled"].default is True
    assert fields["polymarket_ws_enabled"].default is True

    settings = SimpleNamespace(
        live_feed_enabled=fields["live_feed_enabled"].default,
        kalshi_ws_enabled=fields["kalshi_ws_enabled"].default,
        polymarket_ws_enabled=fields["polymarket_ws_enabled"].default,
    )
    plan = background_loop_plan(settings)
    assert "kalshi_ws" in plan
    assert "polymarket_ws" in plan


class _RaisingStream(MarketStream):
    """A stream whose every session raises — proves run() never propagates it."""

    source = "raiser"

    def __init__(self) -> None:
        super().__init__(reconnect_cap_sec=0.01, heartbeat_timeout_sec=0.05)
        self.attempts = 0

    def _ws_url(self) -> str:
        return "wss://example/raiser"

    def _subscribe_frames(self):
        return []

    def parse_frame(self, raw):
        return []

    async def _run_session(self, callback):
        self.attempts += 1
        if self.attempts >= 2:
            self.stop()  # let the run loop exit after we prove it survived one raise
        raise RuntimeError("stream boom")


@pytest.mark.asyncio
async def test_stream_error_does_not_propagate():
    stream = _RaisingStream()

    async def _cb(_event):  # pragma: no cover - never called (sessions raise first)
        return None

    # run() must swallow the RuntimeError, back off, retry, then exit cleanly on stop.
    await asyncio.wait_for(stream.run(_cb), timeout=5)

    assert stream.attempts >= 2
    assert stream.state is ConnectionState.STOPPED
