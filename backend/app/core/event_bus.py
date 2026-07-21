"""In-process async pub/sub event bus — a Redis Streams substitute needing no Redis.

The deployed free tier runs with ``REDIS_URL=redis://disabled``, so cross-process
fan-out is unavailable. This bus fans domain events to in-process async subscribers
(the ``/feed`` WebSocket, workers) within a single process.

Design contract:
- ``publish(topic, payload)`` NEVER blocks the caller and NEVER raises. It is a plain
  synchronous call so it is safe from any context (a hot tick path, a sync callback).
- Each subscriber owns a bounded queue. On overflow the OLDEST item is dropped (so a
  slow consumer can never apply backpressure to the publisher) and the drop is logged.
- ``subscribe(topic)`` returns an async-iterable ``Subscription``; ``async for`` yields
  payloads until the subscription is closed.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

# Canonical wired-in domain topics. Any string works; these are documentation.
TOPICS = ("market.tick", "signal.new", "order.filled", "market.resolved")

_DEFAULT_MAXSIZE = 256


class Subscription:
    """An async-iterable view over one subscriber's bounded queue."""

    def __init__(self, bus: EventBus, topic: str, maxsize: int) -> None:
        self._bus = bus
        self._topic = topic
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    def _deliver(self, payload: Any) -> None:
        """Non-blocking enqueue with drop-oldest overflow. Called by the publisher."""
        try:
            self._queue.put_nowait(payload)
            return
        except asyncio.QueueFull:
            pass
        # Overflow: discard the stalest item to make room, then enqueue the new one.
        try:
            self._queue.get_nowait()
        except asyncio.QueueEmpty:  # pragma: no cover - queue drained concurrently
            pass
        self.dropped += 1
        msg = "event_bus: dropped oldest on '%s' (slow subscriber, %d total)"
        if self.dropped == 1 or self.dropped % 1000 == 0:
            logger.warning(msg, self._topic, self.dropped)
        else:
            logger.debug(msg, self._topic, self.dropped)
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:  # pragma: no cover - would require concurrent fill
            pass

    async def get(self) -> Any:
        return await self._queue.get()

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        return await self._queue.get()

    def close(self) -> None:
        self._bus._unsubscribe(self._topic, self)


class EventBus:
    """Topic-keyed fan-out to in-process async subscribers."""

    def __init__(self, maxsize: int = _DEFAULT_MAXSIZE) -> None:
        self._maxsize = maxsize
        self._subs: dict[str, set[Subscription]] = defaultdict(set)

    def subscribe(self, topic: str) -> Subscription:
        sub = Subscription(self, topic, self._maxsize)
        self._subs[topic].add(sub)
        return sub

    def _unsubscribe(self, topic: str, sub: Subscription) -> None:
        subs = self._subs.get(topic)
        if not subs:
            return
        subs.discard(sub)
        if not subs:
            self._subs.pop(topic, None)

    def publish(self, topic: str, payload: Any) -> None:
        """Fan ``payload`` to every subscriber of ``topic``. Never blocks; never raises."""
        for sub in list(self._subs.get(topic, ())):
            sub._deliver(payload)

    def subscriber_count(self, topic: str) -> int:
        return len(self._subs.get(topic, ()))


_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the process-wide singleton bus."""
    return _bus
