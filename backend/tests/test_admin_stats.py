"""Loop V23 A3 — admin stats aggregates + 30s cache."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import admin_stats as admin_stats_mod
from app.db.models import (
    ForecastLog,
    ForecastMode,
    ForecastScore,
    ForecastSource,
    Forecaster,
    Market,
    MarketStatus,
    PaperOrder,
    Platform,
    User,
)
from app.db.session import get_db
from app.main import app

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}
WRONG_HEADERS = {"X-Admin-API-Key": "wrong-key"}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    admin_stats_mod.invalidate_stats_cache()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    admin_stats_mod.invalidate_stats_cache()


@pytest.mark.asyncio
async def test_stats_requires_admin(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/stats", headers=WRONG_HEADERS)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stats_aggregates_and_cache(db_session):
    now = datetime.now(timezone.utc)
    user = User(email="stats@example.com", hashed_password="x", paper_balance=Decimal("100"))
    db_session.add(user)
    await db_session.flush()

    db_session.add_all(
        [
            Market(
                slug="stats-open",
                title="Open",
                question="?",
                status=MarketStatus.OPEN,
            ),
            Market(
                slug="stats-locked",
                title="Locked",
                question="?",
                status=MarketStatus.LOCKED,
            ),
            Market(
                slug="stats-resolved",
                title="Resolved",
                question="?",
                status=MarketStatus.RESOLVED,
            ),
            Market(
                slug="stats-cancelled",
                title="Cancelled",
                question="?",
                status=MarketStatus.CANCELLED,
            ),
        ]
    )
    db_session.add(
        PaperOrder(
            user_id=user.id,
            slug="stats-open",
            side="YES",
            outcome="yes",
            shares=Decimal("1"),
            price=Decimal("0.5"),
            cost=Decimal("0.5"),
            action="BUY",
            created_at=now - timedelta(hours=1),
        )
    )
    db_session.add(
        PaperOrder(
            user_id=user.id,
            slug="stats-open",
            side="NO",
            outcome="no",
            shares=Decimal("1"),
            price=Decimal("0.4"),
            cost=Decimal("0.4"),
            action="BUY",
            created_at=now - timedelta(days=3),
        )
    )

    forecaster = Forecaster(
        token_hash="a" * 64,
        recovery_code_hash="b" * 64,
    )
    db_session.add(forecaster)
    await db_session.flush()

    # ForecastLog needs external_market — create minimal via raw insert if needed.
    # Prefer skip graded path if ExternalMarket is heavy: seed external market.
    from app.db.models import ExternalMarket, ExternalMarketStatus

    ext = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=f"ext-{uuid4().hex[:8]}",
        title="ext",
        status=ExternalMarketStatus.OPEN,
    )
    db_session.add(ext)
    await db_session.flush()

    flog = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=ext.id,
        seq=1,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.55"),
        mode=ForecastMode.LIVE,
        source=ForecastSource.WEB,
    )
    db_session.add(flog)
    await db_session.flush()
    db_session.add(
        ForecastScore(
            forecast_id=flog.id,
            actual_outcome=1,
            user_brier=Decimal("0.100000"),
            synthetic_pnl=Decimal("0"),
        )
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)
        assert first.status_code == 200
        body = first.json()
        assert body["paper_trading_only"] is True
        assert body["cached"] is False
        assert body["cache_ttl_sec"] == 30.0
        assert body["users"] >= 1
        assert body["markets_by_status"]["open"] >= 1
        assert body["markets_by_status"]["locked"] >= 1
        assert body["markets_by_status"]["resolved"] >= 1
        assert body["markets_by_status"]["cancelled"] >= 1
        assert body["trades"]["last_24h"] >= 1
        assert body["trades"]["last_7d"] >= 2
        assert body["forecasts"]["locked"] >= 1
        assert body["forecasts"]["graded"] >= 1
        assert body["table_counts"]["users"] >= 1
        assert body["table_counts"]["markets"] >= 4
        assert body["table_counts"]["paper_orders"] >= 2

        second = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)
        assert second.status_code == 200
        assert second.json()["cached"] is True
        # cached payload stable
        assert second.json()["generated_at"] == body["generated_at"]
