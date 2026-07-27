"""Loop117 — D6: latest_run on list/featured + polymarket ws heartbeat contract.

Mirrors the repo's test conventions: inline ASGITransport client with a get_db
dependency override (as in tests/test_loop107_scanner_seeds.py) and stdlib
unittest.mock + monkeypatch (pytest-mock is not a dev dependency here).
Scanner/ScannerRun status fields are plain strings ("active", "completed").
"""
import asyncio
import itertools
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.streams.base import StreamEvent, StreamEventKind
from app.db.models import Scanner, ScannerRun
from app.db.session import get_db
from app.main import _polymarket_stream_loop, app


@pytest.mark.asyncio
async def test_list_and_featured_attach_latest_run(db_session: AsyncSession):
    scanner = Scanner(
        name="Test Scanner",
        description="A test scanner",
        owner="user-123",
        spec={"steps": []},
        version=1,
        status="active",
        is_public=True,
        is_featured=True,
        cooldown_minutes=60,
    )
    db_session.add(scanner)
    await db_session.flush()

    run1 = ScannerRun(
        scanner_id=scanner.id,
        started_at=datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
        status="completed",
        result={"repairs": []},
    )
    run2 = ScannerRun(
        scanner_id=scanner.id,
        started_at=datetime(2025, 1, 1, 13, 0, tzinfo=UTC),
        status="completed",
        result={"repairs": [{"market_slug": "test"}]},
    )
    db_session.add(run1)
    db_session.add(run2)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        resp_list = await client.get("/api/v1/scanners/")
        assert resp_list.status_code == 200
        data_list = resp_list.json()
        assert len(data_list) > 0
        sc = next(s for s in data_list if s["id"] == str(scanner.id))
        assert sc["latest_run"] is not None
        assert sc["latest_run"]["id"] == str(run2.id)
        assert sc["latest_run"]["repairs_count"] == 1

        resp_feat = await client.get("/api/v1/scanners/featured")
        assert resp_feat.status_code == 200
        data_feat = resp_feat.json()
        assert len(data_feat["items"]) > 0
        scf = next(s for s in data_feat["items"] if s["id"] == str(scanner.id))
        assert scf["latest_run"] is not None
        assert scf["latest_run"]["id"] == str(run2.id)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_latest_run_absent_is_null_not_omitted(db_session: AsyncSession):
    scanner = Scanner(
        name="Empty Scanner",
        description="A test scanner without runs",
        owner="user-123",
        spec={"steps": []},
        version=1,
        status="active",
        is_public=True,
        is_featured=True,
        cooldown_minutes=60,
    )
    db_session.add(scanner)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        resp_list = await client.get("/api/v1/scanners/")
        assert resp_list.status_code == 200
        data_list = resp_list.json()
        sc = next(s for s in data_list if s["id"] == str(scanner.id))
        assert "latest_run" in sc
        assert sc["latest_run"] is None

        resp_feat = await client.get("/api/v1/scanners/featured")
        assert resp_feat.status_code == 200
        data_feat = resp_feat.json()
        scf = next(s for s in data_feat["items"] if s["id"] == str(scanner.id))
        assert "latest_run" in scf
        assert scf["latest_run"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_polymarket_ws_beats_inside_stream(monkeypatch):
    mock_record = MagicMock()
    monkeypatch.setattr("app.main.record_heartbeat", mock_record)
    # _polymarket_stream_loop imports these inside the function body, so the
    # patch targets are the source modules, not app.main.
    monkeypatch.setattr(
        "app.data.streams.runner.polymarket_token_slug_map",
        AsyncMock(return_value={"token_123": "slug-123"}),
    )
    monkeypatch.setattr(
        "app.data.streams.runner._persist_tick_event",
        AsyncMock(return_value=None),
    )

    # Strictly advancing pseudo-clock, >60s per step, so every callback
    # crosses the heartbeat threshold no matter who else reads time.time
    # (e.g. logging LogRecord creation); the repeat tail keeps stray
    # consumers from exhausting the side effect.
    time_mock = MagicMock(
        side_effect=itertools.chain(
            (0, 61, 122, 183, 244, 305, 366, 427, 488, 549),
            itertools.repeat(610),
        )
    )
    monkeypatch.setattr("time.time", time_mock)

    class FakeStream:
        def __init__(self, *args, **kwargs):
            self.state = MagicMock(value="connected")
            self._stopped = asyncio.Event()

        async def run(self, callback):
            event = StreamEvent(
                market_slug="slug-123",
                kind=StreamEventKind.TICK,
                payload={"yes": 0.5},
                source="polymarket.ws",
                received_ts=datetime.now(UTC),
            )
            for _ in range(3):
                await callback(event)
            self._stopped.set()

    monkeypatch.setattr("app.data.streams.polymarket_ws.PolymarketMarketStream", FakeStream)

    # Suppress sleep; must be awaitable or the loop's restart path spins.
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    await _polymarket_stream_loop()

    calls = mock_record.mock_calls
    # Expecting: 1 for starting, then at least 2 for message batches
    assert len(calls) >= 3
    assert call("polymarket_ws", detail="stream loop starting") in calls
    assert call("polymarket_ws", detail="messages-since-last:1") in calls
