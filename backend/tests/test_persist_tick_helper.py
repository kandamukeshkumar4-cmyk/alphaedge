"""T01 — shared persist_and_publish_tick helper used by poller and streams."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.broadcast import hub
from app.workers.price_feed_worker import persist_and_publish_tick


class _FakeDB:
    def __init__(self, prev_yes: float | None):
        self._prev = prev_yes
        self.added: list = []

    async def scalar(self, *_args, **_kwargs):
        return self._prev

    def add(self, obj) -> None:
        self.added.append(obj)


@pytest.mark.asyncio
async def test_first_tick_persists_and_publishes(monkeypatch):
    published = []
    monkeypatch.setattr(hub, "publish", AsyncMock(side_effect=lambda slug, p: published.append((slug, p))))
    db = _FakeDB(prev_yes=None)

    moved = await persist_and_publish_tick(db, slug="m", yes=0.42, source="kalshi.ws")

    assert moved is True
    assert len(db.added) == 1
    slug, payload = published[0]
    assert slug == "m"
    assert payload["yes"] == 0.42
    assert payload["no"] == 0.58
    assert payload["alert"] is False
    assert "side" not in payload  # guardrail: no order keys leak to the hub


@pytest.mark.asyncio
async def test_unchanged_tick_publishes_but_does_not_persist(monkeypatch):
    monkeypatch.setattr(hub, "publish", AsyncMock())
    db = _FakeDB(prev_yes=0.42)

    moved = await persist_and_publish_tick(db, slug="m", yes=0.4201, source="kalshi.ws")

    assert moved is False
    assert db.added == []  # below epsilon -> no new row


@pytest.mark.asyncio
async def test_large_move_sets_alert(monkeypatch):
    published = []
    monkeypatch.setattr(hub, "publish", AsyncMock(side_effect=lambda slug, p: published.append(p)))
    db = _FakeDB(prev_yes=0.40)

    await persist_and_publish_tick(db, slug="m", yes=0.50, source="kalshi.ws")

    assert published[0]["alert"] is True


@pytest.mark.asyncio
async def test_out_of_range_yes_is_clamped(monkeypatch):
    published = []
    monkeypatch.setattr(hub, "publish", AsyncMock(side_effect=lambda slug, p: published.append(p)))
    db = _FakeDB(prev_yes=None)

    await persist_and_publish_tick(db, slug="m", yes=1.5, source="kalshi.ws")

    assert published[0]["yes"] == 1.0
    assert published[0]["no"] == 0.0
