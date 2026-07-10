"""J02 — alerts feed tests (read-only composition of signal_events)."""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, SignalEvent
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
            Market(slug=SLUG_A, title="A", question="A?", status=MarketStatus.OPEN),
            Market(slug=SLUG_B, title="B", question="B?", status=MarketStatus.OPEN),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            # Alert-family events with citation fields.
            SignalEvent(
                signal_type="news:mispricing",
                platform="seed",
                market_id=SLUG_A,
                headline_eligible=True,
                payload={
                    "id": "abc123",
                    "news_id": "n1",
                    "news_url": "https://example.com/n1",
                    "headline": "Star out",
                    "model_p": 0.7,
                    "market_p": 0.55,
                },
                created_at=now - timedelta(hours=1),
            ),
            SignalEvent(
                signal_type="delta:price_jump",
                platform="stream",
                market_id=SLUG_A,
                headline_eligible=False,
                payload={"direction": "up", "magnitude": 0.08},
                created_at=now - timedelta(hours=2),
            ),
            SignalEvent(
                signal_type="screener:momentum",
                platform="seed",
                market_id=SLUG_B,
                headline_eligible=False,
                payload={},
                created_at=now - timedelta(hours=3),
            ),
            SignalEvent(
                signal_type="arb",
                platform="seed",
                market_id=SLUG_B,
                headline_eligible=False,
                payload={},
                created_at=now - timedelta(hours=4),
            ),
            # NON-family event: must never surface.
            SignalEvent(
                signal_type="alignment",
                platform="seed",
                market_id=SLUG_A,
                headline_eligible=False,
                payload={},
                created_at=now - timedelta(minutes=30),
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_public_anon_all_families_newest_first(db_session):
    await _seed(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/alerts/feed")
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "all"
    types = [i["signal_type"] for i in body["items"]]
    # Four alert-family events, alignment excluded, newest-first.
    assert types == ["news:mispricing", "delta:price_jump", "screener:momentum", "arb"]
    assert "alignment" not in types


@pytest.mark.asyncio
async def test_citation_fields_present(db_session):
    await _seed(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/alerts/feed", params={"slugs": SLUG_A})
    items = r.json()["items"]
    news = next(i for i in items if i["signal_type"] == "news:mispricing")
    cit = news["citation"]
    assert cit["signal_id"] == "abc123"
    assert cit["news_url"] == "https://example.com/n1"
    assert cit["headline"] == "Star out"
    assert cit["model_p"] == 0.7
    assert cit["market_p"] == 0.55
    # A delta event has no news citation — honest None, not fabricated.
    delta = next(i for i in items if i["signal_type"] == "delta:price_jump")
    assert delta["citation"]["news_url"] is None
    assert delta["citation"]["headline"] is None


@pytest.mark.asyncio
async def test_explicit_slug_filter(db_session):
    await _seed(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/alerts/feed", params={"slugs": SLUG_B})
    body = r.json()
    assert body["scope"] == "explicit"
    assert {i["slug"] for i in body["items"]} == {SLUG_B}


@pytest.mark.asyncio
async def test_since_filter(db_session):
    await _seed(db_session)
    since = (datetime.now(UTC) - timedelta(hours=2, minutes=30)).isoformat()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/alerts/feed", params={"since": since})
    types = [i["signal_type"] for i in r.json()["items"]]
    # Only events newer than 2h30m ago: news (1h) + delta (2h).
    assert types == ["news:mispricing", "delta:price_jump"]


@pytest.mark.asyncio
async def test_authed_defaults_to_watchlist(db_session):
    await _seed(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "alerts-wl@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post("/api/v1/watchlist", json={"slug": SLUG_B}, headers=headers)
        r = await client.get("/api/v1/alerts/feed", headers=headers)
    body = r.json()
    assert body["scope"] == "watchlist"
    assert {i["slug"] for i in body["items"]} == {SLUG_B}


@pytest.mark.asyncio
async def test_authed_empty_watchlist_is_honest_empty(db_session):
    await _seed(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "alerts-empty-wl@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get("/api/v1/alerts/feed", headers=headers)
    body = r.json()
    assert body["scope"] == "watchlist"
    assert body["items"] == []
