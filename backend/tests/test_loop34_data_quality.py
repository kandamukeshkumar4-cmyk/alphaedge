"""Loop V34 — data-quality audit issue classes (fixture tests, no network).

Issue classes from D1:
1. Duplicate PM prop titles across fixtures → event-title fold
2. Stale open past lock_at / missing-upstream linger → lock hygiene
3. Category miscounts (politics vs world cup, FIFA taxonomy)
4. Orphan weather signal_events (raw Kalshi ticker market_id)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.data_quality.hygiene import (
    canonical_kalshi_market_id,
    fold_display_title,
    rekey_orphan_signal_market_ids,
    signal_title_fallback,
)
from app.db.models import Market, MarketStatus, SignalEvent
from app.db.session import get_db
from app.main import app
from app.services.live_market_ingest import (
    LiveMarketIngestService,
    categorize,
    display_title_for_payload,
)
from app.services.weather_desk import weather_scan_to_events
from app.workers.price_feed_worker import lapse_expired_markets
from app.workers.tasks import run_weather_scan


# ── 1) title fold ────────────────────────────────────────────────────────────


def test_fold_display_title_appends_distinguisher():
    assert fold_display_title("Kylian Mbappé: 1+ goals", "France vs Morocco") == (
        "France vs Morocco: Kylian Mbappé: 1+ goals"
    )
    # No-op when empty / equal / yes-no
    assert fold_display_title("Will X happen?", None) == "Will X happen?"
    assert fold_display_title("Same", "same") == "Same"
    assert fold_display_title("Will X happen?", "Yes") == "Will X happen?"


def test_display_title_for_payload_folds_event_context():
    payload = {
        "question": "Kylian Mbappé: 1+ goals",
        "slug": "fifwc-fra-mar-goals-mbappe",
        "_event_title": "France vs Morocco",
    }
    assert display_title_for_payload(payload) == (
        "France vs Morocco: Kylian Mbappé: 1+ goals"
    )


@pytest.mark.asyncio
async def test_pm_ingest_folds_event_title_into_card_async(db_session):
    class Fake:
        def list_active_markets_via_events(self, *, tag_slug, limit=25, min_volume=0.0):
            if tag_slug != "soccer":
                return []
            return [
                {
                    "slug": "fifwc-fra-mar-2026-07-09-goals-kylian-mbappe-gte1",
                    "question": "Kylian Mbappé: 1+ goals",
                    "conditionId": "0x1",
                    "outcomes": json.dumps(["Yes", "No"]),
                    "outcomePrices": json.dumps(["0.4", "0.6"]),
                    "volume24hr": 50_000,
                    "volumeNum": 50_000,
                    "endDate": "2026-07-09T22:00:00Z",
                    "active": True,
                    "closed": False,
                    "_event_title": "France vs Morocco",
                    "clobTokenIds": json.dumps(["tok-a", "tok-b"]),
                },
                {
                    "slug": "fifwc-fra-esp-2026-07-14-goals-kylian-mbappe-gte1",
                    "question": "Kylian Mbappé: 1+ goals",
                    "conditionId": "0x2",
                    "outcomes": json.dumps(["Yes", "No"]),
                    "outcomePrices": json.dumps(["0.35", "0.65"]),
                    "volume24hr": 40_000,
                    "volumeNum": 40_000,
                    "endDate": "2026-07-14T22:00:00Z",
                    "active": True,
                    "closed": False,
                    "_event_title": "France vs Spain",
                    "clobTokenIds": json.dumps(["tok-c", "tok-d"]),
                },
            ]

    service = LiveMarketIngestService(db_session, connector=Fake())
    summary = await service.sync_curated_markets(min_volume_24h=10_000.0, total_limit=50)
    assert summary["imported"] == 2

    titles = {
        m.title
        for m in (
            await db_session.execute(select(Market).where(Market.source == "polymarket"))
        ).scalars()
    }
    assert "France vs Morocco: Kylian Mbappé: 1+ goals" in titles
    assert "France vs Spain: Kylian Mbappé: 1+ goals" in titles
    # Distinct — no exact-title collision
    assert len(titles) == 2


# ── 2) lifecycle ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lapse_expired_markets_idempotent(db_session):
    now = datetime.now(UTC)
    m = Market(
        slug="ks-stale-open",
        title="Stale",
        question="Stale?",
        category="Sports",
        icon="🏟️",
        volume=1,
        traders=0,
        market_count=1,
        description="",
        resolution="",
        status=MarketStatus.OPEN,
        lock_at=now - timedelta(hours=6),
        source="kalshi",
        external_slug="KXSTALE-1",
    )
    db_session.add(m)
    await db_session.flush()

    assert await lapse_expired_markets(db_session) >= 1
    await db_session.refresh(m)
    assert m.status == MarketStatus.LOCKED
    # Second pass is a no-op (idempotent)
    assert await lapse_expired_markets(db_session) == 0


# ── 3) category ──────────────────────────────────────────────────────────────


def test_categorize_politics_beats_world_cup():
    cat, _ = categorize("President Trump to Attend World Cup Final?", None)
    assert cat == "Politics"


def test_categorize_world_cup_is_fifa_bucket():
    cat, icon = categorize("Will Egypt win the 2026 FIFA World Cup?", "Sports")
    assert cat == "FIFA WC2026"
    assert icon == "⚽"


def test_kalshi_climate_maps_to_weather():
    from app.services.kalshi_live_ingest import _map_kalshi_category

    assert _map_kalshi_category("Climate and Weather") == ("Weather", "🌡️")
    assert _map_kalshi_category("weather") == ("Weather", "🌡️")
    assert _map_kalshi_category("science and technology") == ("Tech", "🔬")


# ── 4) orphan signal_events ──────────────────────────────────────────────────


def test_canonical_kalshi_market_id():
    assert canonical_kalshi_market_id("KXHIGHNY-26JUL16-B91.5") == (
        "ks-kxhighny-26jul16-b91.5"
    )
    assert canonical_kalshi_market_id("ks-kxhighny-26jul16-b91.5") == (
        "ks-kxhighny-26jul16-b91.5"
    )


def test_weather_events_use_local_slug():
    events = weather_scan_to_events(
        [
            {
                "city": "Miami",
                "date": "2026-07-16",
                "buckets": [
                    {
                        "ticker": "KXHIGHMIA-26JUL16-B96.5",
                        "bucket": "96.5 or below",
                        "edge": 0.20,
                        "model_probability": 0.4,
                        "market_yes": 0.2,
                        "read": "model rich",
                    }
                ],
            }
        ]
    )
    assert len(events) == 1
    assert events[0]["market_id"] == "ks-kxhighmia-26jul16-b96.5"
    assert events[0]["payload"]["raw_market_id"] == "KXHIGHMIA-26JUL16-B96.5"


@pytest.mark.asyncio
async def test_rekey_orphan_signal_market_ids_idempotent(db_session):
    # Pre-existing orphan shape from prod (raw ticker)
    db_session.add(
        SignalEvent(
            signal_type="delta:weather_edge",
            platform="kalshi",
            market_id="KXHIGHMIA-26JUL16-B96.5",
            headline_eligible=True,
            payload={"city": "Miami", "edge": 0.2},
        )
    )
    await db_session.flush()

    first = await rekey_orphan_signal_market_ids(db_session, limit=50)
    assert first["rekeyed"] == 1
    row = (
        await db_session.execute(select(SignalEvent))
    ).scalar_one()
    assert row.market_id == "ks-kxhighmia-26jul16-b96.5"
    assert row.payload.get("raw_market_id") == "KXHIGHMIA-26JUL16-B96.5"

    second = await rekey_orphan_signal_market_ids(db_session, limit=50)
    assert second["rekeyed"] == 0


@pytest.mark.asyncio
async def test_weather_scan_joins_when_market_exists(db_session):
    """End-to-end: emit with ks- slug + Market row ⇒ signals API has title."""
    slug = "ks-kxhighny-26jul06-t89"
    db_session.add(
        Market(
            slug=slug,
            title="NYC high temp bucket",
            question="NYC high ≥ 89?",
            category="Weather",
            icon="🌡️",
            volume=100,
            traders=0,
            market_count=1,
            description="",
            resolution="",
            status=MarketStatus.OPEN,
            source="kalshi",
            external_slug="KXHIGHNY-26JUL06-T89",
        )
    )
    await db_session.flush()

    cities = [
        {
            "city": "New York",
            "date": "2026-07-06",
            "forecast_high_f": 88.0,
            "buckets": [
                {
                    "ticker": "KXHIGHNY-26JUL06-T89",
                    "bucket": "89 or above",
                    "model_probability": 0.30,
                    "market_yes": 0.12,
                    "edge": 0.18,
                    "read": "model rich",
                }
            ],
        }
    ]
    assert await run_weather_scan(db_session, cities) == 1

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/signals/events", params={"limit": 10})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    items = resp.json()["items"]
    weather = [i for i in items if i["signal_type"] == "delta:weather_edge"]
    assert weather
    assert weather[0]["market_id"] == slug
    assert weather[0]["market_title"] == "NYC high temp bucket"


def test_signal_title_fallback_uses_city():
    assert signal_title_fallback(None, {"city": "Austin", "bucket": "88.5 or below"}) == (
        "Austin high: 88.5 or below"
    )
    assert signal_title_fallback("Joined Title", {"city": "Austin"}) == "Joined Title"
