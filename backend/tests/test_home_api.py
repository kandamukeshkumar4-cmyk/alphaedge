"""M01 — personalized home aggregate tests (Loop V8).

``GET /api/v1/home`` — PUBLIC GET with OPTIONAL JWT. Composes recent signals
(H03 citations), the L02 digest, model-A/B readiness, and top markets. Authed
callers also get their K03 watchlist count + recent watchlist alerts. Honest
empties everywhere; anon omits (nulls/empties) the personal sections.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, OddsSnapshot, SignalEvent
from app.db.session import get_db
from app.main import app

SLUG_A = "nba-2025-01-15-lal-bos"
SLUG_B = "nba-2025-01-16-gsw-mia"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_token(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "securepass1"}
    )
    assert r.status_code == 201
    return r.json()["access_token"]


async def _seed(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Market(
                slug=SLUG_A, title="A", question="A?",
                status=MarketStatus.OPEN, volume=5000,
            ),
            Market(
                slug=SLUG_B, title="B", question="B?",
                status=MarketStatus.OPEN, volume=9000,
            ),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=SLUG_A,
                implied_yes=Decimal("0.50"),
                captured_at=now - timedelta(hours=4),
            ),
            OddsSnapshot(
                market_slug=SLUG_A,
                implied_yes=Decimal("0.52"),
                captured_at=now - timedelta(minutes=5),
            ),
            OddsSnapshot(
                market_slug=SLUG_B,
                implied_yes=Decimal("0.45"),
                captured_at=now - timedelta(hours=4),
            ),
            OddsSnapshot(
                market_slug=SLUG_B,
                implied_yes=Decimal("0.55"),
                captured_at=now - timedelta(minutes=4),
            ),
            SignalEvent(
                signal_type="news:mispricing",
                platform="seed",
                market_id=SLUG_A,
                payload={
                    "id": "sig-1",
                    "news_id": "n-1",
                    "news_url": "https://example.com/n1",
                    "headline": "Star player questionable",
                    "model_p": 0.62,
                    "market_p": 0.50,
                },
                headline_eligible=True,
                created_at=now - timedelta(hours=1),
            ),
            SignalEvent(
                signal_type="arb",
                platform="seed",
                market_id=SLUG_B,
                payload={},
                created_at=now - timedelta(hours=2),
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_anon_shape_omits_watchlist(db_session):
    await _seed(db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/home")
    assert r.status_code == 200
    body = r.json()
    # Non-personal sections present.
    assert body["authenticated"] is False
    assert body["paper_trading_only"] is True
    assert body["signal_only"] is True
    assert isinstance(body["signals"], list) and len(body["signals"]) == 2
    # H03 citation fields carried through.
    top = body["signals"][0]
    assert top["citation"]["news_url"] == "https://example.com/n1"
    assert top["citation"]["model_p"] == 0.62
    # Digest + model_ab + top_markets composed.
    assert body["digest"]["total"] == 2
    assert body["model_ab"]["ab_ready"] in (True, False)
    assert body["model_ab"]["applied"] is False
    assert [m["slug"] for m in body["top_markets"]] == [SLUG_B, SLUG_A]  # 24h movement desc
    # Personal sections nulled/empty for anon.
    assert body["watchlist_count"] is None
    assert body["watchlist_alerts"] == []


@pytest.mark.asyncio
async def test_authed_enrichment_present(db_session):
    await _seed(db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup_token(client, "home-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        # Watch SLUG_A so its alert (news:mispricing) is in the watchlist feed.
        add = await client.post(
            "/api/v1/watchlist", json={"slug": SLUG_A}, headers=headers
        )
        assert add.status_code == 201
        r = await client.get("/api/v1/home", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["watchlist_count"] == 1
    assert len(body["watchlist_alerts"]) == 1
    assert body["watchlist_alerts"][0]["slug"] == SLUG_A


@pytest.mark.asyncio
async def test_honest_empty_db(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/home")
    assert r.status_code == 200
    body = r.json()
    assert body["signals"] == []
    assert body["digest"]["total"] == 0
    assert body["digest"]["families"] == {}
    assert body["top_markets"] == []
    assert body["watchlist_count"] is None
    assert body["watchlist_alerts"] == []
