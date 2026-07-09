"""T12 — public analyst API: feed, track record, claims, latency, pagination."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    AnalystBrief,
    AnalystEvalAggregate,
    BriefClaim,
    Market,
    MarketStatus,
    OddsSnapshot,
)
from app.db.session import get_db
from app.main import app

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)


@asynccontextmanager
async def _client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def _seed_brief(db, slug="pm-a", kind="brief", with_claim=True, tools_used=None):
    brief = AnalystBrief(
        id=uuid4(), market_slug=slug, kind=kind, headline=f"{slug} headline",
        body_markdown="body", citations=[{"kind": "model", "ref": "m"}],
        tools_used=tools_used,
        generator="fallback", model_version="lgbm-1", prompt_version="v1",
        created_at=NOW,
    )
    db.add(brief)
    await db.flush()
    if with_claim:
        db.add(
            BriefClaim(
                id=uuid4(), brief_id=brief.id, market_slug=slug, direction="up",
                horizon_minutes=60, confidence=Decimal("0.7"), status="correct",
                created_at=NOW, resolved_at=NOW,
            )
        )
        await db.flush()
    return brief


@pytest.mark.asyncio
async def test_list_briefs_empty(db_session):
    async with _client(db_session) as client:
        r = await client.get("/api/v1/briefs")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.asyncio
async def test_list_briefs_with_items_and_claim(db_session):
    await _seed_brief(db_session, "pm-a")
    async with _client(db_session) as client:
        r = await client.get("/api/v1/briefs")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["market_slug"] == "pm-a"
    assert item["claim"]["direction"] == "up"
    assert item["claim"]["status"] == "correct"


@pytest.mark.asyncio
async def test_briefs_filter_by_kind(db_session):
    await _seed_brief(db_session, "pm-a", kind="brief", with_claim=False)
    await _seed_brief(db_session, "__digest__", kind="digest", with_claim=False)
    async with _client(db_session) as client:
        r = await client.get("/api/v1/briefs", params={"kind": "digest"})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "digest"


@pytest.mark.asyncio
async def test_briefs_filter_by_category(db_session):
    db_session.add(
        Market(id=uuid4(), slug="pm-a", title="t", question="q",
                status=MarketStatus.OPEN, source="polymarket", category="Politics")
    )
    await _seed_brief(db_session, "pm-a", with_claim=False)
    async with _client(db_session) as client:
        hit = await client.get("/api/v1/briefs", params={"category": "Politics"})
        miss = await client.get("/api/v1/briefs", params={"category": "Crypto"})
    assert hit.json()["total"] == 1
    assert miss.json()["total"] == 0


@pytest.mark.asyncio
async def test_pagination_bounds_reject_out_of_range(db_session):
    async with _client(db_session) as client:
        too_big = await client.get("/api/v1/briefs", params={"limit": 500})
        negative = await client.get("/api/v1/briefs", params={"offset": -1})
    assert too_big.status_code == 422
    assert negative.status_code == 422


@pytest.mark.asyncio
async def test_get_brief_by_id_and_404(db_session):
    brief = await _seed_brief(db_session, "pm-a", with_claim=False)
    async with _client(db_session) as client:
        found = await client.get(f"/api/v1/briefs/{brief.id}")
        missing = await client.get(f"/api/v1/briefs/{uuid4()}")
    assert found.status_code == 200 and found.json()["market_slug"] == "pm-a"
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_brief_api_exposes_tools_used_when_persisted(db_session):
    tools_used = [
        {"tool": "get_order_book_summary", "spread": 0.02},
        {"tool": "get_price_history", "points": 5},
    ]
    brief = await _seed_brief(
        db_session,
        "pm-a",
        with_claim=False,
        tools_used=tools_used,
    )
    async with _client(db_session) as client:
        found = await client.get(f"/api/v1/briefs/{brief.id}")
        listing = await client.get("/api/v1/briefs")

    assert found.status_code == 200
    assert found.json()["tools_used"] == tools_used
    assert listing.json()["items"][0]["tools_used"] == tools_used


@pytest.mark.asyncio
async def test_track_record(db_session):
    db_session.add(
        AnalystEvalAggregate(
            id=uuid4(), dimension="overall", dim_key="all", window_days=0,
            n=40, accuracy=Decimal("0.62"), brier=Decimal("0.21"), provisional=False,
            computed_at=NOW,
        )
    )
    await db_session.flush()
    async with _client(db_session) as client:
        r = await client.get("/api/v1/analyst/track-record")
    aggs = r.json()["aggregates"]
    assert len(aggs) == 1
    assert aggs[0]["accuracy"] == 0.62 and aggs[0]["provisional"] is False


@pytest.mark.asyncio
async def test_track_record_claims_transparency(db_session):
    await _seed_brief(db_session, "pm-a")  # creates a correct claim
    async with _client(db_session) as client:
        r = await client.get("/api/v1/analyst/track-record/claims", params={"status": "correct"})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "correct"


@pytest.mark.asyncio
async def test_market_latency(db_session):
    db_session.add(
        OddsSnapshot(
            id=uuid4(), market_slug="pm-lat", implied_yes=Decimal("0.5"),
            source="polymarket-live", captured_at=NOW - timedelta(seconds=30),
            book="polymarket", market_type="binary", outcome_name="Yes",
            price=Decimal("0.5"),
        )
    )
    await db_session.flush()
    async with _client(db_session) as client:
        r = await client.get("/api/v1/markets/pm-lat/latency")
        empty = await client.get("/api/v1/markets/nope/latency")
    body = r.json()
    assert body["live"] is True
    assert body["staleness_seconds"] is not None and body["staleness_seconds"] >= 30
    assert empty.json() == {
        "market_slug": "nope", "last_snapshot_at": None,
        "staleness_seconds": None, "source": None, "live": False,
    }


@pytest.mark.asyncio
async def test_endpoints_reachable_under_rate_limit_middleware(db_session):
    # SlowAPIMiddleware is installed app-wide (enforces the default limit); a single
    # request must pass through cleanly. Per-route x-ratelimit headers require an
    # explicit @limiter decorator (a UI nicety, deferred) — reachability is the check.
    async with _client(db_session) as client:
        r = await client.get("/api/v1/briefs")
    assert r.status_code == 200
