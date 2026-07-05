"""T01 finding #2 / T02 — degrade-to-polling: which background loops start.

Proves that disabling a WS stream does NOT remove the REST polling loops
(price_feed / live_ingest / live_tick), so the app degrades to polling.
"""
from __future__ import annotations

from types import SimpleNamespace

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
