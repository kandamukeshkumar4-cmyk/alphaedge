"""Tests for BroadcastHub fan-out."""
from __future__ import annotations

import asyncio

import pytest

from app.core.broadcast import BroadcastHub


@pytest.mark.asyncio
async def test_subscribe_returns_queue():
    hub = BroadcastHub()
    q = hub.subscribe("test-slug")
    assert q is not None


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    hub = BroadcastHub()
    q = hub.subscribe("test-slug")
    payload = {"slug": "test-slug", "yes": 0.6, "no": 0.4, "ts": 1000}
    await hub.publish("test-slug", payload)
    result = await asyncio.wait_for(q.get(), timeout=1.0)
    assert result == payload


@pytest.mark.asyncio
async def test_publish_fans_out_to_multiple_subscribers():
    hub = BroadcastHub()
    q1 = hub.subscribe("test-slug")
    q2 = hub.subscribe("test-slug")
    payload = {"slug": "test-slug", "yes": 0.7, "no": 0.3, "ts": 2000}
    await hub.publish("test-slug", payload)
    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert r1 == payload
    assert r2 == payload


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue():
    hub = BroadcastHub()
    q = hub.subscribe("test-slug")
    hub.unsubscribe("test-slug", q)
    await hub.publish("test-slug", {"slug": "test-slug", "yes": 0.5, "no": 0.5, "ts": 3000})
    assert q.empty()


@pytest.mark.asyncio
async def test_publish_no_subscribers_is_noop():
    hub = BroadcastHub()
    # Should not raise even with no subscribers
    await hub.publish("empty-slug", {"slug": "empty-slug", "yes": 0.5, "no": 0.5, "ts": 4000})


@pytest.mark.asyncio
async def test_publish_drops_for_full_queue():
    hub = BroadcastHub()
    q = hub.subscribe("test-slug")
    # Fill the queue to capacity (maxsize=32)
    for i in range(32):
        await hub.publish("test-slug", {"slug": "test-slug", "yes": 0.5, "no": 0.5, "ts": i})
    # One more publish should be dropped without raising
    await hub.publish("test-slug", {"slug": "test-slug", "yes": 0.9, "no": 0.1, "ts": 99})
    assert q.full()
