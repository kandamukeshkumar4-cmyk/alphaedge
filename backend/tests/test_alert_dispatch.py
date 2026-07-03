"""T09 — alert dispatch: fan-out, disabled-flags no external calls, dedupe."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import Alert
from app.services.alert_dispatch import AlertDispatchService, reset_alert_dedupe
from app.signals.alignment import AlignmentLayer, AlignmentScore


def _settings(**over):
    base = dict(
        alerts_telegram_enabled=False,
        telegram_bot_token="",
        telegram_chat_id="",
        alerts_webhook_url="",
    )
    base.update(over)
    return SimpleNamespace(**base)


class _RecordingTransport:
    def __init__(self):
        self.calls = []

    async def __call__(self, url, json_body):
        self.calls.append((url, json_body))


@pytest.fixture(autouse=True)
def _clear_dedupe():
    reset_alert_dedupe()
    yield
    reset_alert_dedupe()


@pytest.mark.asyncio
async def test_dispatch_writes_alert_and_publishes(db_session, monkeypatch):
    published = []
    from app.core import broadcast

    async def _fake_pub(channel, payload):
        published.append((channel, payload))

    monkeypatch.setattr(broadcast.hub, "publish", _fake_pub)

    transport = _RecordingTransport()
    service = AlertDispatchService(db_session, settings=_settings(), transport=transport)
    ok = await service.dispatch(
        alert_type="alignment", message="hi", payload={"market_slug": "m"},
        dedupe_key="k1",
    )
    assert ok is True
    await db_session.flush()

    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 1
    assert published and published[0][0] == "alerts"
    # external channels disabled -> transport never called
    assert transport.calls == []


@pytest.mark.asyncio
async def test_disabled_flags_make_no_external_calls(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    transport = _RecordingTransport()
    service = AlertDispatchService(db_session, settings=_settings(), transport=transport)
    await service.dispatch(alert_type="brief", message="x", payload={}, dedupe_key="k2")
    assert transport.calls == []


@pytest.mark.asyncio
async def test_telegram_enabled_calls_transport_with_capped_message(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    transport = _RecordingTransport()
    settings = _settings(
        alerts_telegram_enabled=True, telegram_bot_token="tok", telegram_chat_id="123"
    )
    service = AlertDispatchService(db_session, settings=settings, transport=transport)
    await service.dispatch(
        alert_type="alignment", message="A" * 800, payload={}, dedupe_key="k3"
    )
    assert len(transport.calls) == 1
    url, body = transport.calls[0]
    assert "api.telegram.org/bottok/sendMessage" in url
    assert len(body["text"]) <= 400


@pytest.mark.asyncio
async def test_webhook_url_calls_transport(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    transport = _RecordingTransport()
    settings = _settings(alerts_webhook_url="https://example.com/hook")
    service = AlertDispatchService(db_session, settings=settings, transport=transport)
    await service.dispatch(alert_type="brief", message="m", payload={"x": 1}, dedupe_key="k4")
    assert len(transport.calls) == 1
    assert transport.calls[0][0] == "https://example.com/hook"


@pytest.mark.asyncio
async def test_dedupe_suppresses_second_dispatch(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    service = AlertDispatchService(db_session, settings=_settings())
    first = await service.dispatch(alert_type="a", message="m", payload={}, dedupe_key="dup")
    second = await service.dispatch(alert_type="a", message="m", payload={}, dedupe_key="dup")
    assert first is True and second is False
    await db_session.flush()
    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 1  # only one row despite two dispatch calls


@pytest.mark.asyncio
async def test_dispatch_alignment_builds_message(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    transport = _RecordingTransport()
    service = AlertDispatchService(db_session, settings=_settings(), transport=transport)
    score = AlignmentScore(
        market_slug="pm-fed", direction="up",
        layers_firing=frozenset({AlignmentLayer.PRICE, AlignmentLayer.WHALE, AlignmentLayer.NEWS}),
        score=3.0, window_sec=600.0,
    )
    ok = await service.dispatch_alignment(score)
    assert ok is True
    await db_session.flush()
    row = await db_session.scalar(select(Alert).where(Alert.alert_type == "alignment"))
    assert "pm-fed" in row.message and "UP" in row.message


async def _noop(*_a, **_k):
    return None
