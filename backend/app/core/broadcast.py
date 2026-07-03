from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from app.observability.metrics import set_ws_clients

logger = logging.getLogger(__name__)


class BroadcastHub:
    """Fan-out hub: publish a price tick to every subscriber for that slug."""

    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[dict]]] = defaultdict(set)

    def subscribe(self, slug: str) -> asyncio.Queue[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=32)
        self._queues[slug].add(q)
        self._sync_ws_clients_gauge()
        return q

    def unsubscribe(self, slug: str, q: asyncio.Queue[dict]) -> None:
        self._queues[slug].discard(q)
        if not self._queues[slug]:
            del self._queues[slug]
        self._sync_ws_clients_gauge()

    def _sync_ws_clients_gauge(self) -> None:
        total = sum(len(queues) for queues in self._queues.values())
        set_ws_clients(total)

    async def publish(self, slug: str, payload: dict) -> None:
        queues = list(self._queues.get(slug, []))
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.debug("Dropping tick for slow subscriber on %s", slug)


hub = BroadcastHub()
