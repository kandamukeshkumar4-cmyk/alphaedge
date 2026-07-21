"""H2 — MarketStream._connect passes max_size=8MiB to websockets.connect."""
from __future__ import annotations

import pytest

from app.data.streams.base import MarketStream, StreamEvent


class _MinimalStream(MarketStream):
    source = "test.min"

    def _ws_url(self) -> str:
        return "wss://example.test/ws"

    def _subscribe_frames(self):
        return []

    def parse_frame(self, raw: str) -> list[StreamEvent]:
        return []


@pytest.mark.asyncio
async def test_connect_passes_max_size_8mib(monkeypatch):
    captured: dict = {}

    async def fake_connect(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    stream = _MinimalStream()
    await stream._connect()

    assert captured["url"] == "wss://example.test/ws"
    assert captured["kwargs"]["open_timeout"] == 15
    assert captured["kwargs"]["max_size"] == 8_388_608
