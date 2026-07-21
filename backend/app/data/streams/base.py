"""Base abstractions for long-lived market data WebSocket streams.

The subclass implements only the exchange-specific bits: which subscribe frames
to send, and how to parse a raw text frame into normalized ``StreamEvent`` values.
The reconnect / heartbeat / resubscribe state machine lives here so every stream
behaves identically under network failure.
"""
from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

StreamCallback = Callable[["StreamEvent"], Awaitable[None]]


class StreamEventKind(str, Enum):
    TICK = "tick"
    ORDERBOOK_DELTA = "orderbook_delta"


class ConnectionState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


@dataclass(frozen=True)
class StreamEvent:
    """One normalized event off a market stream.

    ``payload`` carries the kind-specific data (e.g. ``{"yes": 0.42}`` for a tick,
    or bid/ask level deltas for an orderbook delta). ``received_ts`` is our clock;
    ``exchange_ts`` is the exchange's if present (used for latency measurement).
    """

    market_slug: str
    kind: StreamEventKind
    payload: dict[str, Any]
    source: str
    received_ts: datetime
    exchange_ts: datetime | None = None

    @property
    def latency_ms(self) -> float | None:
        if self.exchange_ts is None:
            return None
        return (self.received_ts - self.exchange_ts).total_seconds() * 1000.0


@dataclass
class _Backoff:
    """Jittered exponential backoff, capped."""

    base_sec: float = 1.0
    cap_sec: float = 60.0
    _attempt: int = field(default=0)

    def reset(self) -> None:
        self._attempt = 0

    def next_delay(self) -> float:
        # Full-jitter: random between 0 and min(cap, base * 2**attempt).
        ceiling = min(self.cap_sec, self.base_sec * (2**self._attempt))
        self._attempt += 1
        return random.uniform(0.0, ceiling)  # noqa: S311 - jitter, not crypto


class MarketStream:
    """Long-lived reconnecting market stream.

    Subclasses override :meth:`_ws_url`, :meth:`_subscribe_frames`, and
    :meth:`parse_frame`. The public entrypoint is :meth:`run`, which never returns
    until :meth:`stop` is called; it survives socket drops by reconnecting.
    """

    source: str = "stream"

    def __init__(
        self,
        *,
        reconnect_cap_sec: float = 60.0,
        heartbeat_timeout_sec: float = 30.0,
    ) -> None:
        self._backoff = _Backoff(cap_sec=max(1.0, reconnect_cap_sec))
        self._heartbeat_timeout = max(1.0, heartbeat_timeout_sec)
        self._state = ConnectionState.IDLE
        self._stopped = asyncio.Event()
        self._last_latency_ms: float | None = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def last_latency_ms(self) -> float | None:
        return self._last_latency_ms

    def stop(self) -> None:
        self._stopped.set()
        self._state = ConnectionState.STOPPED

    # --- subclass hooks -------------------------------------------------

    def _ws_url(self) -> str:  # pragma: no cover - trivial in subclass
        raise NotImplementedError

    def _subscribe_frames(self) -> Sequence[str]:  # pragma: no cover
        raise NotImplementedError

    def parse_frame(self, raw: str) -> list[StreamEvent]:  # pragma: no cover
        """Pure parse: raw text frame -> zero or more StreamEvents.

        MUST NOT raise on malformed input — return ``[]`` and let the caller log.
        """
        raise NotImplementedError

    async def _connect(self):  # pragma: no cover - requires network
        """Open the socket. Split out so tests can inject a fake connector."""
        import websockets

        return await websockets.connect(
            self._ws_url(), open_timeout=15, max_size=8 * 1024 * 1024
        )

    # --- run loop -------------------------------------------------------

    async def run(self, callback: StreamCallback) -> None:
        """Consume the stream forever, dispatching parsed events to ``callback``."""
        while not self._stopped.is_set():
            self._state = ConnectionState.CONNECTING
            try:
                await self._run_session(callback)
                self._backoff.reset()
            except asyncio.CancelledError:
                self.stop()
                raise
            except Exception as error:  # noqa: BLE001 - resilience is the whole point
                logger.warning("[%s] stream session ended: %s", self.source, error)
            if self._stopped.is_set():
                break
            self._state = ConnectionState.RECONNECTING
            delay = self._backoff.next_delay()
            logger.info("[%s] reconnecting in %.1fs", self.source, delay)
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
        self._state = ConnectionState.STOPPED

    async def _run_session(self, callback: StreamCallback) -> None:
        conn = await self._connect()
        self._state = ConnectionState.CONNECTED
        try:
            for frame in self._subscribe_frames():
                await conn.send(frame)
            while not self._stopped.is_set():
                try:
                    raw = await asyncio.wait_for(
                        conn.recv(), timeout=self._heartbeat_timeout
                    )
                except asyncio.TimeoutError as exc:
                    raise ConnectionError("heartbeat timeout") from exc
                await self._dispatch(raw, callback)
        finally:
            close = getattr(conn, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result

    async def _dispatch(self, raw: Any, callback: StreamCallback) -> None:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        if not isinstance(raw, str):
            return
        try:
            events = self.parse_frame(raw)
        except Exception:  # noqa: BLE001 - defensive: parser must never kill the loop
            logger.debug("[%s] frame parse raised, skipping", self.source, exc_info=True)
            return
        for event in events:
            if event.latency_ms is not None:
                self._last_latency_ms = event.latency_ms
            try:
                await callback(event)
            except Exception:  # noqa: BLE001 - one bad event never drops the stream
                logger.warning(
                    "[%s] callback failed for %s", self.source, event.market_slug,
                    exc_info=True,
                )


def utcnow() -> datetime:
    return datetime.now(UTC)
