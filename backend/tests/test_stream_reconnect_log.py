"""H4 — reconnect session-ended / reconnecting logs rate-capped."""
from __future__ import annotations

import logging

import pytest

from app.data.streams.base import MarketStream, StreamEvent


async def _noop(_event: StreamEvent) -> None:
    return None


class _ScriptedStream(MarketStream):
    """``_run_session`` follows ``script``: 'fail' | 'msg_then_fail' | 'stop'."""

    source = "cap.test"

    def __init__(self, script: list[str]) -> None:
        super().__init__(reconnect_cap_sec=0.001, heartbeat_timeout_sec=0.05)
        self._script = list(script)
        self._idx = 0

    def _ws_url(self) -> str:
        return "wss://example.test/cap"

    def _subscribe_frames(self):
        return []

    def parse_frame(self, raw: str) -> list[StreamEvent]:
        return []

    async def _run_session(self, callback) -> None:
        action = self._script[self._idx]
        self._idx += 1
        if action == "stop":
            self.stop()
            return
        if action == "msg_then_fail":
            self._session_received_message = True
            raise RuntimeError("disconnect-after-msg")
        raise RuntimeError(f"fail-{self._idx}")


def _ended_records(caplog):
    return [
        r
        for r in caplog.records
        if "stream session ended" in r.getMessage()
    ]


@pytest.mark.asyncio
async def test_reconnect_warning_on_1_and_10(caplog):
    # 10 failing sessions, then clean stop
    script = ["fail"] * 10 + ["stop"]
    stream = _ScriptedStream(script)

    with caplog.at_level(logging.DEBUG, logger="app.data.streams.base"):
        await stream.run(_noop)

    ended = _ended_records(caplog)
    assert len(ended) == 10
    assert ended[0].levelno == logging.WARNING
    for r in ended[1:9]:
        assert r.levelno == logging.DEBUG
    assert ended[9].levelno == logging.WARNING
    assert stream._reconnect_attempt == 10


@pytest.mark.asyncio
async def test_reconnect_counter_resets_after_successful_session(caplog):
    # 3 fails (attempts 1-3), then a session that got a message, then fail again
    script = ["fail", "fail", "fail", "msg_then_fail", "fail", "stop"]
    stream = _ScriptedStream(script)

    with caplog.at_level(logging.DEBUG, logger="app.data.streams.base"):
        await stream.run(_noop)

    ended = _ended_records(caplog)
    assert len(ended) == 5
    # attempts 1,2,3 then reset → 1 (msg_then_fail), then 2 (fail)
    assert ended[0].levelno == logging.WARNING  # attempt 1
    assert ended[1].levelno == logging.DEBUG  # attempt 2
    assert ended[2].levelno == logging.DEBUG  # attempt 3
    assert ended[3].levelno == logging.WARNING  # reset → attempt 1
    assert ended[4].levelno == logging.DEBUG  # attempt 2
    assert stream._reconnect_attempt == 2
