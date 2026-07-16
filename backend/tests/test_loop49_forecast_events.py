"""Loop V49 — forecast lifecycle WS frames + watcher notifications.

Covers E1 (forecasts hub channel) and E2 (watchlist notify on lock/resolve):
* multiplex registration
* never-raises isolation (a failing publish never breaks lock/resolve/score)
* watcher targeting via catalog slug join
* dedupe per user+market+event
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1 import ws as ws_mod
from app.core.broadcast import hub
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    Market,
    MarketStatus,
    Notification,
    Platform,
    User,
    Watchlist,
)
from app.services import forecast_events
from app.services.external_market_service import ExternalMarketService
from app.services.notification_producers import (
    notify_watchers_forecast_locked,
    notify_watchers_market_resolved,
)
from app.services.scoring_service import ScoringService
from sqlalchemy import select


# ---------------------------------------------------------------------------
# E1 — WS forecasts channel
# ---------------------------------------------------------------------------


def test_ws_feed_registers_forecasts_topic():
    assert "forecasts" in ws_mod._FEED_TOPICS


@pytest.mark.asyncio
async def test_activity_feed_routes_forecasts_channel(monkeypatch):
    monkeypatch.setattr(
        ws_mod, "get_settings", lambda: SimpleNamespace(paper_trading_only=True)
    )

    class _ForecastWS:
        def __init__(self) -> None:
            self.sent: list[dict] = []

        async def accept(self) -> None:
            pass

        async def send_json(self, data: dict) -> None:
            self.sent.append(data)
            if data.get("channel") == "forecasts":
                raise WebSocketDisconnect()

        async def close(self, code: int | None = None) -> None:
            pass

    fake = _ForecastWS()
    task = asyncio.create_task(ws_mod.activity_feed(fake))
    await asyncio.sleep(0.05)
    await hub.publish(
        "forecasts",
        {
            "type": "forecast.locked",
            "external_market_id": "em-1",
            "title": "Will it rain?",
        },
    )
    await asyncio.wait_for(task, timeout=2.0)

    frame = next(m for m in fake.sent if m.get("channel") == "forecasts")
    assert frame["type"] == "forecast.locked"
    assert frame["title"] == "Will it rain?"
    assert not any(t in hub._queues for t in ws_mod._FEED_TOPICS)


@pytest.mark.asyncio
async def test_publish_forecast_events_never_raise_and_land_on_hub(monkeypatch):
    captured: list[tuple[str, dict]] = []

    async def _capture(topic: str, payload: dict) -> None:
        captured.append((topic, payload))

    monkeypatch.setattr(hub, "publish", _capture)

    await forecast_events.publish_forecast_locked(
        forecast_id=uuid4(),
        external_market_id=uuid4(),
        platform="polymarket",
        external_id="ext-a",
        title="A",
        user_probability=0.61,
        mode="live",
        locked_at=datetime.now(UTC),
    )
    await forecast_events.publish_market_resolved(
        external_market_id=uuid4(),
        platform="polymarket",
        external_id="ext-b",
        title="B",
        winning_outcome=1,
        resolved_at=datetime.now(UTC),
    )
    await forecast_events.publish_forecast_scored(
        external_market_id=uuid4(),
        platform="polymarket",
        external_id="ext-c",
        title="C",
        count=2,
    )

    assert [c[0] for c in captured] == ["forecasts", "forecasts", "forecasts"]
    types = [c[1]["type"] for c in captured]
    assert types == ["forecast.locked", "market.resolved", "forecast.scored"]
    assert captured[0][1]["user_probability"] == pytest.approx(0.61)
    assert captured[1][1]["winning_outcome"] == 1
    assert captured[2][1]["count"] == 2


@pytest.mark.asyncio
async def test_publish_hooks_swallow_hub_failures(monkeypatch):
    async def _boom(*_a, **_k):
        raise RuntimeError("hub down")

    monkeypatch.setattr(hub, "publish", _boom)
    # Must not raise.
    await forecast_events.publish_forecast_locked(
        forecast_id="f",
        external_market_id="m",
        platform="polymarket",
        external_id="x",
        title="t",
    )
    await forecast_events.publish_market_resolved(
        external_market_id="m",
        platform="polymarket",
        external_id="x",
        title="t",
        winning_outcome=0,
    )
    await forecast_events.publish_forecast_scored(
        external_market_id="m",
        platform="polymarket",
        external_id="x",
        title="t",
        count=1,
    )


@pytest.mark.asyncio
async def test_resolve_survives_failing_forecast_publish(db_session, monkeypatch):
    """E3 isolation: a broken WS publish must not abort ExternalMarket.resolve."""

    async def _boom(*_a, **_k):
        raise RuntimeError("ws exploded")

    monkeypatch.setattr(
        "app.services.forecast_events.publish_market_resolved", _boom
    )
    monkeypatch.setattr(
        "app.services.notification_producers.notify_watchers_market_resolved",
        AsyncMock(return_value=0),
    )

    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="pm-v49-resolve-iso",
        title="Isolation market",
        status=ExternalMarketStatus.OPEN,
        close_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(market)
    await db_session.flush()

    resolved = await ExternalMarketService(db_session).resolve(market.id, 1)
    assert resolved.status == ExternalMarketStatus.RESOLVED
    assert resolved.winning_outcome == 1


@pytest.mark.asyncio
async def test_score_survives_failing_forecast_publish(db_session, monkeypatch):
    """E3 isolation: a broken WS publish must not abort ScoringService."""
    from app.db.models import Forecaster

    async def _boom(*_a, **_k):
        raise RuntimeError("ws exploded")

    monkeypatch.setattr(
        "app.services.forecast_events.publish_forecast_scored", _boom
    )

    close_at = datetime.now(UTC) - timedelta(hours=2)
    forecaster = Forecaster(token_hash="tok-v49", recovery_code_hash="rec-v49")
    db_session.add(forecaster)
    await db_session.flush()

    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="pm-v49-score-iso",
        title="Score iso",
        status=ExternalMarketStatus.RESOLVED,
        winning_outcome=1,
        close_at=close_at,
        resolved_at=close_at,
    )
    db_session.add(market)
    await db_session.flush()

    db_session.add(
        ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal("0.65"),
            mode=ForecastMode.LIVE,
            locked_at=close_at - timedelta(hours=3),
        )
    )
    await db_session.flush()

    scored = await ScoringService(db_session).score_market(market)
    assert scored == 1


# ---------------------------------------------------------------------------
# E2 — watcher notifications
# ---------------------------------------------------------------------------


async def _seed_catalog_and_external(
    db_session,
    *,
    catalog_slug: str,
    external_id: str,
    title: str = "V49 watched market",
) -> tuple[Market, ExternalMarket]:
    market = Market(
        slug=catalog_slug,
        title=title,
        question=title,
        category="Sports",
        status=MarketStatus.OPEN,
        source="polymarket",
        external_slug=external_id,
        external_id=external_id,
    )
    db_session.add(market)
    em = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=external_id,
        title=title,
        status=ExternalMarketStatus.OPEN,
        close_at=datetime.now(UTC) + timedelta(hours=2),
    )
    db_session.add(em)
    await db_session.flush()
    return market, em


@pytest.mark.asyncio
async def test_watcher_notified_on_forecast_locked(db_session):
    catalog_slug = "v49-watch-lock"
    external_id = "pm-v49-watch-lock"
    _catalog, em = await _seed_catalog_and_external(
        db_session, catalog_slug=catalog_slug, external_id=external_id
    )

    watcher = User(email="v49-watcher@example.com", hashed_password="x")
    stranger = User(email="v49-stranger@example.com", hashed_password="x")
    db_session.add_all([watcher, stranger])
    await db_session.flush()
    db_session.add(Watchlist(user_id=watcher.id, slug=catalog_slug))
    await db_session.flush()

    forecast = SimpleNamespace(user_probability=Decimal("0.72"))
    n = await notify_watchers_forecast_locked(
        external_market=em, forecast=forecast, session=db_session
    )
    assert n == 1
    await db_session.commit()

    rows = (
        await db_session.scalars(select(Notification).order_by(Notification.created_at))
    ).all()
    assert len(rows) == 1
    assert rows[0].user_id == watcher.id
    assert rows[0].type == "forecast_locked"
    assert rows[0].link == f"/markets/{catalog_slug}"
    assert "0.720" in rows[0].body or "0.72" in rows[0].body


@pytest.mark.asyncio
async def test_watcher_notified_on_market_resolved(db_session):
    catalog_slug = "v49-watch-resolve"
    external_id = "pm-v49-watch-resolve"
    _catalog, em = await _seed_catalog_and_external(
        db_session, catalog_slug=catalog_slug, external_id=external_id
    )
    em.status = ExternalMarketStatus.RESOLVED
    em.winning_outcome = 1
    em.resolved_at = datetime.now(UTC)

    watcher = User(email="v49-resolve-watch@example.com", hashed_password="x")
    db_session.add(watcher)
    await db_session.flush()
    db_session.add(Watchlist(user_id=watcher.id, slug=catalog_slug))
    await db_session.flush()

    n = await notify_watchers_market_resolved(external_market=em, session=db_session)
    assert n == 1
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.user_id == watcher.id)
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].type == "market_resolved"
    assert "YES" in rows[0].body


@pytest.mark.asyncio
async def test_non_watcher_not_notified(db_session):
    catalog_slug = "v49-no-watch"
    external_id = "pm-v49-no-watch"
    _catalog, em = await _seed_catalog_and_external(
        db_session, catalog_slug=catalog_slug, external_id=external_id
    )
    user = User(email="v49-nowatch@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    # No Watchlist row.

    n = await notify_watchers_forecast_locked(
        external_market=em, forecast=None, session=db_session
    )
    assert n == 0
    count = len(
        (
            await db_session.scalars(
                select(Notification).where(Notification.user_id == user.id)
            )
        ).all()
    )
    assert count == 0


@pytest.mark.asyncio
async def test_watcher_notify_dedupes_per_user_market_event(db_session):
    catalog_slug = "v49-dedupe"
    external_id = "pm-v49-dedupe"
    _catalog, em = await _seed_catalog_and_external(
        db_session, catalog_slug=catalog_slug, external_id=external_id
    )
    watcher = User(email="v49-dedupe@example.com", hashed_password="x")
    db_session.add(watcher)
    await db_session.flush()
    db_session.add(Watchlist(user_id=watcher.id, slug=catalog_slug))
    await db_session.flush()

    first = await notify_watchers_forecast_locked(
        external_market=em, forecast=None, session=db_session
    )
    second = await notify_watchers_forecast_locked(
        external_market=em, forecast=None, session=db_session
    )
    assert first == 1
    assert second == 0
    rows = (
        await db_session.scalars(
            select(Notification).where(
                Notification.user_id == watcher.id,
                Notification.type == "forecast_locked",
            )
        )
    ).all()
    assert len(rows) == 1

    # Different event type is not deduped against lock.
    em.winning_outcome = 0
    r1 = await notify_watchers_market_resolved(external_market=em, session=db_session)
    r2 = await notify_watchers_market_resolved(external_market=em, session=db_session)
    assert r1 == 1
    assert r2 == 0


@pytest.mark.asyncio
async def test_watcher_notify_never_raises(db_session, monkeypatch):
    async def _boom(*_a, **_k):
        raise RuntimeError("db gone")

    monkeypatch.setattr(
        "app.services.notification_producers.catalog_slug_for_external_market",
        _boom,
    )
    n = await notify_watchers_forecast_locked(
        external_market=SimpleNamespace(external_id="x", title="t"),
        session=db_session,
    )
    assert n == 0
