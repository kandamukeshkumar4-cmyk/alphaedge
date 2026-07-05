"""Kalshi live mirror read APIs: candles and latest price."""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, OddsSnapshot
from app.db.session import get_db
from app.main import app

KALSHI_SLUG = "ks-kxwcgame-26jun12canbih-can"


@pytest.mark.asyncio
async def test_kalshi_candles_and_latest_price(db_session):
    db_session.add(
        Market(
            slug=KALSHI_SLUG,
            title="Canada vs Bosnia and Herzegovina",
            question="Canada — Canada vs Bosnia",
            category="Sports",
            icon="soccer",
            volume=1_000_000,
            source="kalshi",
            external_slug="KXWCGAME-26JUN12CANBIH-CAN",
            status=MarketStatus.OPEN,
        )
    )
    captured = datetime(2026, 6, 12, 16, 0, tzinfo=UTC)
    db_session.add(
        OddsSnapshot(
            market_slug=KALSHI_SLUG,
            implied_yes=0.54,
            captured_at=captured,
            source="kalshi.rest",
        )
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            candles = await client.get(
                f"/api/v1/markets/{KALSHI_SLUG}/candles",
                params={"points": 10},
            )
            latest = await client.get(f"/api/v1/markets/{KALSHI_SLUG}/prices/latest")
            missing = await client.get("/api/v1/markets/ks-unknown-slug/prices/latest")
    finally:
        app.dependency_overrides.clear()

    assert candles.status_code == 200
    body = candles.json()
    assert body["source"] == "live"
    assert len(body["candles"]) >= 1
    assert body["candles"][-1]["close"] == pytest.approx(0.54)

    assert latest.status_code == 200
    price = latest.json()
    assert price["yes"] == pytest.approx(0.54)
    assert price["source"] == "db"

    assert missing.status_code == 404
