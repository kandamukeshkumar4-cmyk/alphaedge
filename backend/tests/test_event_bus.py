"""In-process event bus (loop2): pub/sub roundtrip, non-blocking, drop-oldest."""
from __future__ import annotations

import asyncio

import pytest

from app.core.event_bus import TOPICS, EventBus, get_event_bus


def test_canonical_topics_present():
    assert set(TOPICS) == {
        "market.tick",
        "signal.new",
        "order.filled",
        "market.resolved",
    }


def test_get_event_bus_is_singleton():
    assert get_event_bus() is get_event_bus()


@pytest.mark.asyncio
async def test_publish_subscribe_roundtrip():
    bus = EventBus()
    sub = bus.subscribe("market.tick")

    bus.publish("market.tick", {"slug": "nba-2025-01-15-lal-bos", "yes": 0.42})

    payload = await asyncio.wait_for(sub.get(), timeout=1)
    assert payload == {"slug": "nba-2025-01-15-lal-bos", "yes": 0.42}


@pytest.mark.asyncio
async def test_async_iteration_yields_events():
    bus = EventBus()
    sub = bus.subscribe("signal.new")

    bus.publish("signal.new", {"n": 1})
    bus.publish("signal.new", {"n": 2})

    seen = []
    async for payload in sub:
        seen.append(payload)
        if len(seen) == 2:
            break
    assert seen == [{"n": 1}, {"n": 2}]


@pytest.mark.asyncio
async def test_publish_does_not_reach_other_topics():
    bus = EventBus()
    tick_sub = bus.subscribe("market.tick")
    bus.subscribe("order.filled")

    bus.publish("order.filled", {"fill": 1})

    # The tick subscriber must not see the order.filled event.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(tick_sub.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_slow_subscriber_does_not_block_publisher():
    # A subscriber that never drains must not slow or block publish().
    bus = EventBus(maxsize=4)
    bus.subscribe("market.tick")  # never consumed

    # publish() is synchronous and must return immediately, far more times than
    # the queue can hold, without ever awaiting or raising.
    for i in range(1000):
        bus.publish("market.tick", {"i": i})

    # A second, live subscriber added afterwards still works normally.
    live = bus.subscribe("market.tick")
    bus.publish("market.tick", {"i": "live"})
    assert await asyncio.wait_for(live.get(), timeout=1) == {"i": "live"}


@pytest.mark.asyncio
async def test_overflow_drops_oldest_and_logs(caplog):
    bus = EventBus(maxsize=3)
    sub = bus.subscribe("market.tick")

    with caplog.at_level("WARNING"):
        for i in range(5):  # 2 more than capacity -> oldest 2 dropped
            bus.publish("market.tick", {"i": i})

    drained = []
    for _ in range(3):
        drained.append(await asyncio.wait_for(sub.get(), timeout=1))

    # Oldest (0, 1) were dropped; newest 3 survive in order.
    assert [p["i"] for p in drained] == [2, 3, 4]
    assert sub.dropped == 2
    assert any("dropped oldest" in rec.message for rec in caplog.records)


def test_close_unsubscribes():
    bus = EventBus()
    sub = bus.subscribe("market.tick")
    assert bus.subscriber_count("market.tick") == 1
    sub.close()
    assert bus.subscriber_count("market.tick") == 0
    # publish after close must be a harmless no-op.
    bus.publish("market.tick", {"x": 1})
