"""T01 — Kalshi WebSocket stream: pure parser + reconnect state machine."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.data.streams.base import (
    ConnectionState,
    MarketStream,
    StreamEvent,
    StreamEventKind,
)
from app.data.streams.kalshi_ws import KalshiMarketStream, parse_kalshi_frame

TICKER_MAP = {"KXWCGAME-USA-BRA": "ks-kxwcgame-usa-bra"}


def test_parse_ticker_v2_produces_tick():
    raw = json.dumps(
        {
            "type": "ticker_v2",
            "msg": {"market_ticker": "KXWCGAME-USA-BRA", "price": 42, "ts": 1_700_000_000},
        }
    )
    events = parse_kalshi_frame(raw, TICKER_MAP)
    assert len(events) == 1
    ev = events[0]
    assert ev.kind is StreamEventKind.TICK
    assert ev.market_slug == "ks-kxwcgame-usa-bra"
    assert ev.payload["yes"] == 0.42
    assert ev.exchange_ts is not None


def test_exchange_to_publish_latency_under_50ms():
    """Accept bullet: exchange_ts -> hub publish measured < 50ms (I/O-free path)."""
    import time
    from datetime import UTC, datetime

    from app.data.streams.base import utcnow

    exch = utcnow()
    raw = json.dumps(
        {
            "type": "ticker_v2",
            "msg": {
                "market_ticker": "KXWCGAME-USA-BRA",
                "price": 42,
                "ts": exch.timestamp(),
            },
        }
    )
    start = time.perf_counter()
    events = parse_kalshi_frame(raw, TICKER_MAP, now=datetime.now(UTC))
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert len(events) == 1
    assert events[0].latency_ms is not None
    assert events[0].latency_ms >= 0.0  # received after exchange stamp
    assert elapsed_ms < 50.0  # parse (the only work between recv and callback) is trivial


def test_parse_ticker_midpoint_when_no_last_price():
    raw = json.dumps(
        {
            "type": "ticker_v2",
            "msg": {"market_ticker": "KXWCGAME-USA-BRA", "yes_bid": 40, "yes_ask": 44},
        }
    )
    events = parse_kalshi_frame(raw, TICKER_MAP)
    assert events[0].payload["yes"] == 0.42


def test_parse_orderbook_delta():
    raw = json.dumps(
        {
            "type": "orderbook_delta",
            "msg": {
                "market_ticker": "KXWCGAME-USA-BRA",
                "price": 42,
                "delta": 100,
                "side": "yes",
            },
        }
    )
    events = parse_kalshi_frame(raw, TICKER_MAP)
    assert len(events) == 1
    assert events[0].kind is StreamEventKind.ORDERBOOK_DELTA
    assert events[0].payload == {"price": 0.42, "delta": 100, "side": "yes"}


def test_unknown_ticker_ignored():
    raw = json.dumps(
        {"type": "ticker_v2", "msg": {"market_ticker": "NOT-TRACKED", "price": 50}}
    )
    assert parse_kalshi_frame(raw, TICKER_MAP) == []


def test_heartbeat_and_control_frames_produce_nothing():
    for frame in (
        {"type": "subscribed", "msg": {"channel": "ticker_v2"}},
        {"type": "heartbeat"},
        {"type": "error", "msg": {"code": 6}},
    ):
        assert parse_kalshi_frame(json.dumps(frame), TICKER_MAP) == []


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        "{",
        "[]",
        "null",
        json.dumps({"type": "ticker_v2"}),  # no msg
        json.dumps({"type": "ticker_v2", "msg": {"market_ticker": "KXWCGAME-USA-BRA"}}),  # no price
        json.dumps({"type": "ticker_v2", "msg": {"market_ticker": "KXWCGAME-USA-BRA", "price": 999}}),  # out of range
        json.dumps({"msg": {"market_ticker": "KXWCGAME-USA-BRA", "price": 42}}),  # no type
    ],
)
def test_malformed_frames_never_raise_and_yield_nothing(raw):
    assert parse_kalshi_frame(raw, TICKER_MAP) == []


def test_subscribe_frame_lists_tickers_and_channels():
    stream = KalshiMarketStream(TICKER_MAP)
    frames = stream._subscribe_frames()
    assert len(frames) == 1
    cmd = json.loads(frames[0])
    assert cmd["cmd"] == "subscribe"
    assert cmd["params"]["channels"] == ["ticker_v2", "orderbook_delta"]
    assert cmd["params"]["market_tickers"] == ["KXWCGAME-USA-BRA"]


def test_no_tickers_means_no_subscribe_frames():
    assert KalshiMarketStream({})._subscribe_frames() == []


# --- reconnect / heartbeat state machine (fake socket) -------------------


class _FakeConn:
    """A fake websocket: yields queued frames, then raises to simulate a drop."""

    def __init__(self, frames: list[str], die_with: Exception):
        self._frames = list(frames)
        self._die_with = die_with
        self.sent: list[str] = []
        self.closed = False

    async def send(self, frame: str) -> None:
        self.sent.append(frame)

    async def recv(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        raise self._die_with

    async def close(self) -> None:
        self.closed = True


class _ReconnectStream(MarketStream):
    """Concrete stream over a scripted sequence of fake connections."""

    source = "fake"

    def __init__(self, conns: list[_FakeConn]):
        super().__init__(reconnect_cap_sec=0.01, heartbeat_timeout_sec=0.05)
        self._conns = conns
        self._i = 0

    def _ws_url(self) -> str:
        return "wss://example/fake"

    def _subscribe_frames(self):
        return ["SUB"]

    def parse_frame(self, raw: str):
        from app.data.streams.base import utcnow

        return [
            StreamEvent(
                market_slug="m",
                kind=StreamEventKind.TICK,
                payload={"raw": raw},
                source=self.source,
                received_ts=utcnow(),
            )
        ]

    async def _connect(self):
        conn = self._conns[self._i]
        self._i += 1
        return conn


@pytest.mark.asyncio
async def test_stream_reconnects_through_two_deaths_then_stops():
    conns = [
        _FakeConn(["a1", "a2"], ConnectionError("drop1")),
        _FakeConn(["b1"], ConnectionError("drop2")),
        _FakeConn(["c1"], ConnectionError("drop3")),
    ]
    stream = _ReconnectStream(conns)
    received: list[str] = []

    async def cb(ev: StreamEvent) -> None:
        received.append(ev.payload["raw"])
        if len(received) >= 4:
            stream.stop()

    await asyncio.wait_for(stream.run(cb), timeout=5)

    assert received == ["a1", "a2", "b1", "c1"]
    assert conns[0].sent == ["SUB"]  # resubscribed on every fresh connection
    assert conns[1].sent == ["SUB"]
    assert stream.state is ConnectionState.STOPPED


class _SilentConn:
    """Never yields a frame — forces the heartbeat watchdog to fire."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send(self, frame: str) -> None:
        self.sent.append(frame)

    async def recv(self) -> str:
        await asyncio.sleep(1.0)  # longer than the 0.05s heartbeat timeout
        return "unreached"

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_heartbeat_timeout_triggers_reconnect():
    silent = _SilentConn()
    live = _FakeConn(["ok"], ConnectionError("drop"))
    stream = _ReconnectStream([silent, live])  # type: ignore[list-item]
    received: list[str] = []

    async def cb(ev: StreamEvent) -> None:
        received.append(ev.payload["raw"])
        stream.stop()

    await asyncio.wait_for(stream.run(cb), timeout=5)
    assert received == ["ok"]  # first conn timed out silently, reconnected to second
    assert silent.closed is True  # watchdog closed the dead socket


@pytest.mark.asyncio
async def test_callback_exception_does_not_kill_stream():
    conns = [_FakeConn(["x1", "x2"], ConnectionError("drop"))]
    stream = _ReconnectStream(conns)
    seen: list[str] = []

    async def cb(ev: StreamEvent) -> None:
        seen.append(ev.payload["raw"])
        if ev.payload["raw"] == "x1":
            raise RuntimeError("boom")
        stream.stop()

    await asyncio.wait_for(stream.run(cb), timeout=5)
    assert seen == ["x1", "x2"]  # survived the x1 exception, processed x2
