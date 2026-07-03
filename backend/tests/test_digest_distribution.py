"""T14 — daily digest distribution: format, disabled-no-calls, per-day dedupe."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import Alert
from app.services.alert_dispatch import reset_alert_dedupe
from app.services.digest_distribution import DigestDistributionService, format_digest

NOW = datetime(2026, 7, 2, 6, 0, tzinfo=UTC)

SUMMARY = {
    "markets_reviewed": ["pm-a", "pm-b"],
    "new_briefs": 3,
    "claims_correct": 5,
    "claims_incorrect": 2,
    "unpriced_news": 4,
    "whale_moves": 7,
}


def _settings(enabled):
    return SimpleNamespace(
        digest_distribution_enabled=enabled,
        alerts_telegram_enabled=False,
        telegram_bot_token="",
        telegram_chat_id="",
        alerts_webhook_url="",
    )


@pytest.fixture(autouse=True)
def _clear_dedupe():
    reset_alert_dedupe()
    yield
    reset_alert_dedupe()


def test_format_digest_is_phone_readable():
    msg = format_digest(SUMMARY, date_str="2026-07-02")
    assert "2 markets" in msg
    assert "3 briefs" in msg
    assert "record 5-2" in msg
    assert len(msg) <= 400


@pytest.mark.asyncio
async def test_disabled_makes_no_alert(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    ok = await DigestDistributionService(db_session, settings=_settings(False)).distribute(
        SUMMARY, now=NOW
    )
    assert ok["dispatched"] is False
    assert ok["channels_sent"] == []
    await db_session.flush()
    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 0


@pytest.mark.asyncio
async def test_enabled_writes_digest_alert(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    ok = await DigestDistributionService(db_session, settings=_settings(True)).distribute(
        SUMMARY, now=NOW
    )
    assert ok["dispatched"] is True
    assert "ws" in ok["channels_sent"]
    await db_session.flush()
    row = await db_session.scalar(select(Alert).where(Alert.alert_type == "digest"))
    assert row is not None
    assert "Daily Brief" in row.message


@pytest.mark.asyncio
async def test_per_day_dedupe(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    service = DigestDistributionService(db_session, settings=_settings(True))
    first = await service.distribute(SUMMARY, now=NOW)
    second = await service.distribute(SUMMARY, now=NOW)  # same day
    assert first["dispatched"] is True and second["dispatched"] is False
    await db_session.flush()
    count = await db_session.scalar(
        select(func.count()).select_from(Alert).where(Alert.alert_type == "digest")
    )
    assert count == 1


@pytest.mark.asyncio
async def test_skipped_summary_is_noop(db_session, monkeypatch):
    monkeypatch.setattr("app.core.broadcast.hub.publish", _noop)
    ok = await DigestDistributionService(db_session, settings=_settings(True)).distribute(
        {"skipped": True, "reason": "digest_exists_today"}, now=NOW
    )
    assert ok["dispatched"] is False
    await db_session.flush()
    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 0


async def _noop(*_a, **_k):
    return None
