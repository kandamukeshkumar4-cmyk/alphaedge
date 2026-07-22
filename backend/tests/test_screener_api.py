"""D3 — community screener API (filter + sort over markets + model edge)."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import ASGITransport, AsyncClient

import pytest

from app.db.models import OddsSnapshot, PredictionLog
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(db_session):
    svc = MarketService(db_session)
    now = datetime.now(UTC)
    high = await svc.create_market(
        slug="scr-high-edge",
        title="High Edge Market",
        question="High edge?",
        category="Sports",
        icon="basketball",
        volume=10000,
        lock_at=now + timedelta(hours=6),
    )
    mid = await svc.create_market(
        slug="scr-mid-vol",
        title="Mid Volume Market",
        question="Mid?",
        category="Sports",
        icon="basketball",
        volume=5000,
        lock_at=now + timedelta(hours=2),
    )
    crypto = await svc.create_market(
        slug="scr-crypto",
        title="Crypto Market",
        question="Crypto?",
        category="Crypto",
        icon="bitcoin",
        volume=8000,
        lock_at=now + timedelta(hours=48),
    )
    low_vol = await svc.create_market(
        slug="scr-low-vol",
        title="Low Volume Market",
        question="Low?",
        category="Sports",
        icon="basketball",
        volume=100,
        lock_at=now + timedelta(hours=1),
    )

    # yes prices: high=0.40, mid=0.50, crypto=0.60, low=0.55
    # model probs: high=0.70 (edge +0.30), mid=0.55 (edge +0.05),
    #              crypto=0.62 (edge +0.02), low=0.80 (edge +0.25)
    # move_24h: high +0.10, mid -0.05, crypto +0.20, low 0.00
    seeds = [
        (high.slug, 0.30, 0.40, 0.70, 0.10),
        (mid.slug, 0.55, 0.50, 0.55, -0.05),
        (crypto.slug, 0.40, 0.60, 0.62, 0.20),
        (low_vol.slug, 0.55, 0.55, 0.80, 0.00),
    ]
    for slug, old_p, new_p, model_p, _move in seeds:
        db_session.add(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=old_p,
                captured_at=now - timedelta(hours=30),
            )
        )
        db_session.add(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=new_p,
                captured_at=now - timedelta(minutes=5),
            )
        )
        db_session.add(
            PredictionLog(
                market_slug=slug,
                predicted_prob=Decimal(str(model_p)),
                confidence=Decimal("0.7"),
                predicted_at=now - timedelta(minutes=1),
            )
        )
    await db_session.flush()
    return {"high": high, "mid": mid, "crypto": crypto, "low": low_vol}


@pytest.mark.asyncio
async def test_screener_filter_and_sort(db_session):
    await _seed(db_session)
    client = await _client_for(db_session)
    try:
        # Default: all, sort volume desc
        all_res = await client.get("/api/v1/screener")
        assert all_res.status_code == 200, all_res.text
        body = all_res.json()
        assert set(body.keys()) == {"items", "total"}
        assert body["total"] == 4
        assert [i["slug"] for i in body["items"]] == [
            "scr-high-edge",
            "scr-crypto",
            "scr-mid-vol",
            "scr-low-vol",
        ]
        keys = {
            "slug",
            "title",
            "category",
            "icon",
            "volume",
            "yes_price",
            "move_24h",
            "model_edge",
            "hours_to_close",
        }
        assert set(body["items"][0].keys()) == keys
        assert body["items"][0]["model_edge"] == pytest.approx(0.30, abs=1e-4)
        assert body["items"][0]["move_24h"] == pytest.approx(0.10, abs=1e-4)

        # Category filter
        sports = await client.get("/api/v1/screener", params={"category": "Sports"})
        assert sports.status_code == 200
        assert sports.json()["total"] == 3
        assert all(i["category"] == "Sports" for i in sports.json()["items"])

        # min_volume
        vol = await client.get("/api/v1/screener", params={"min_volume": 5000})
        assert vol.json()["total"] == 3
        assert "scr-low-vol" not in {i["slug"] for i in vol.json()["items"]}

        # min_edge (absolute)
        edged = await client.get("/api/v1/screener", params={"min_edge": 0.20})
        assert edged.status_code == 200
        edged_slugs = {i["slug"] for i in edged.json()["items"]}
        assert edged_slugs == {"scr-high-edge", "scr-low-vol"}

        # max_hours_to_close
        soon = await client.get("/api/v1/screener", params={"max_hours_to_close": 3})
        assert soon.status_code == 200
        soon_slugs = {i["slug"] for i in soon.json()["items"]}
        assert soon_slugs == {"scr-mid-vol", "scr-low-vol"}

        # sort=edge (abs desc)
        by_edge = await client.get("/api/v1/screener", params={"sort": "edge"})
        assert [i["slug"] for i in by_edge.json()["items"]] == [
            "scr-high-edge",  # 0.30
            "scr-low-vol",  # 0.25
            "scr-mid-vol",  # 0.05
            "scr-crypto",  # 0.02
        ]

        # sort=close_time (soonest first)
        by_close = await client.get("/api/v1/screener", params={"sort": "close_time"})
        close_order = [i["slug"] for i in by_close.json()["items"]]
        assert close_order[0] == "scr-low-vol"
        assert close_order[1] == "scr-mid-vol"
        assert close_order[-1] == "scr-crypto"

        # sort=move24h (abs desc)
        by_move = await client.get("/api/v1/screener", params={"sort": "move24h"})
        assert [i["slug"] for i in by_move.json()["items"]] == [
            "scr-crypto",  # 0.20
            "scr-high-edge",  # 0.10
            "scr-mid-vol",  # 0.05
            "scr-low-vol",  # 0.00
        ]

        # limit
        limited = await client.get("/api/v1/screener", params={"limit": 2})
        assert len(limited.json()["items"]) == 2
        assert limited.json()["total"] == 4

        bad = await client.get("/api/v1/screener", params={"sort": "nope"})
        assert bad.status_code == 400
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
