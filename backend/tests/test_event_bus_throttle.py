"""H3 — event_bus slow-subscriber warnings throttled to 1st and every 1000th drop."""
from __future__ import annotations

import logging

import pytest

from app.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_drop_warning_throttled(caplog):
    bus = EventBus(maxsize=2)
    bus.subscribe("market.tick")  # never drained

    with caplog.at_level(logging.WARNING, logger="app.core.event_bus"):
        # Fill queue (2), then overflow ~999 times -> dropped == 999
        # First drop warns; drops 2..999 are debug-only at WARNING filter.
        for i in range(2 + 999):
            bus.publish("market.tick", {"i": i})

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "slow subscriber, 1 total" in warnings[0].getMessage()

        # 1000th drop triggers another WARNING
        bus.publish("market.tick", {"i": "thousand"})
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert "slow subscriber, 1000 total" in warnings[1].getMessage()
