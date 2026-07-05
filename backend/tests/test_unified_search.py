"""
Tests for the U01 unified market search.

Coverage:
- Ranking: title match quality, open-first status, volume desc
- Cross-platform mixing (AlphaEdge + Polymarket + Kalshi source labels)
- Empty query returns all markets (up to limit)
- No-results state for unmatchable query
- /api/v1/search HTTP endpoint

No live external calls — all data comes from the test DB.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.schemas.market import UnifiedMarketSearchResult
from app.services.market_service import MarketService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_markets(db_session):
    """Seed a cross-platform set of markets for search tests."""
    svc = MarketService(db_session)
    lock = datetime.now(timezone.utc) + timedelta(days=7)

    # Open, high volume, AlphaEdge seed
    m1 = await svc.create_market(
        slug="nba-search-lakers-celtics",
        title="Lakers vs Celtics Championship",
        question="Will the Lakers win the championship?",
        category="NBA",
        volume=500_000,
        traders=1200,
        lock_at=lock,
    )

    # Open, lower volume, AlphaEdge seed
    m2 = await svc.create_market(
        slug="nba-search-warriors-bulls",
        title="Warriors vs Bulls Finals",
        question="Will the Warriors win?",
        category="NBA",
        volume=100_000,
        traders=300,
        lock_at=lock,
    )

    # Open, Polymarket source
    m3 = await svc.create_market(
        slug="btc-100k-polymarket",
        title="BTC Above 100K by Dec",
        question="Will BTC reach $100k?",
        category="Crypto",
        volume=2_000_000,
        traders=5000,
        lock_at=lock,
    )
    # Manually set source to simulate Polymarket-ingested market
    from sqlalchemy import update
    from app.db.models import Market
    await db_session.execute(
        update(Market).where(Market.slug == "btc-100k-polymarket").values(source="polymarket")
    )

    # Open, Kalshi source
    m4 = await svc.create_market(
        slug="fed-rate-kalshi",
        title="Fed Rate Cut in September",
        question="Will the Fed cut rates in September?",
        category="Economics",
        volume=800_000,
        traders=2000,
        lock_at=lock,
    )
    await db_session.execute(
        update(Market).where(Market.slug == "fed-rate-kalshi").values(source="kalshi")
    )

    # Resolved market (should rank below open)
    m5 = await svc.create_market(
        slug="nba-search-resolved-game",
        title="Lakers Championship 2024 (Resolved)",
        question="Did the Lakers win?",
        category="NBA",
        volume=900_000,
        traders=3000,
        lock_at=lock,
    )
    from app.db.models import MarketStatus
    from sqlalchemy import update
    await db_session.execute(
        update(Market)
        .where(Market.slug == "nba-search-resolved-game")
        .values(status=MarketStatus.RESOLVED.value)
    )

    await db_session.flush()
    return [m1, m2, m3, m4, m5]


# ---------------------------------------------------------------------------
# Unit tests on service layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_empty_query_returns_all_markets(db_session):
    """Empty query returns all seeded markets up to the limit."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    results = await svc.search_markets(q=None, limit=50)

    slugs = [r.slug for r in results]
    assert "nba-search-lakers-celtics" in slugs
    assert "btc-100k-polymarket" in slugs
    assert "fed-rate-kalshi" in slugs


@pytest.mark.asyncio
async def test_search_no_results_for_unmatchable_query(db_session):
    """A query with no matching title returns an empty list."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    results = await svc.search_markets(q="xyzzy_unmatchable_q1234", limit=20)

    assert results == []


@pytest.mark.asyncio
async def test_search_cross_platform_mixing(db_session):
    """Results include markets from multiple platforms in one response."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    results = await svc.search_markets(q=None, limit=50)
    platforms = {r.platform for r in results}

    # We seeded Polymarket and Kalshi markets; all three platforms should appear.
    assert "Polymarket" in platforms
    assert "Kalshi" in platforms
    # The seed/AlphaEdge markets are also present
    assert "AlphaEdge" in platforms


@pytest.mark.asyncio
async def test_search_ranking_open_before_resolved(db_session):
    """Open markets rank above resolved markets even with higher volume."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    # "Lakers" matches both nba-search-lakers-celtics (open) and
    # nba-search-resolved-game (resolved, higher volume at 900k).
    results = await svc.search_markets(q="Lakers", limit=20)
    assert len(results) >= 2

    open_idx = next(
        (i for i, r in enumerate(results) if r.slug == "nba-search-lakers-celtics"), None
    )
    resolved_idx = next(
        (i for i, r in enumerate(results) if r.slug == "nba-search-resolved-game"), None
    )
    assert open_idx is not None
    assert resolved_idx is not None
    assert open_idx < resolved_idx, (
        "Open market should rank before resolved even with lower volume"
    )


@pytest.mark.asyncio
async def test_search_ranking_volume_within_same_status(db_session):
    """Within same status bucket, higher volume ranks first."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    # All NBA markets that are open: lakers (500k) vs warriors (100k)
    results = await svc.search_markets(q="vs", limit=20)
    open_nba = [r for r in results if r.status == "open" and r.category == "NBA"]
    assert len(open_nba) >= 2

    lakers_idx = next(i for i, r in enumerate(results) if r.slug == "nba-search-lakers-celtics")
    warriors_idx = next(i for i, r in enumerate(results) if r.slug == "nba-search-warriors-bulls")
    assert lakers_idx < warriors_idx, "Higher volume should rank first within same status"


@pytest.mark.asyncio
async def test_search_title_word_match_ranks_above_partial(db_session):
    """Exact word-boundary match ranks above mid-word match."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    # "Fed" is a leading word in "Fed Rate Cut..." (exact match rank=0)
    # Also contained mid-word in nothing else; let's check the Fed market leads
    results = await svc.search_markets(q="Fed", limit=20)
    assert len(results) >= 1
    assert results[0].slug == "fed-rate-kalshi"


@pytest.mark.asyncio
async def test_search_result_shape(db_session):
    """Each result is a UnifiedMarketSearchResult with the required fields."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    results = await svc.search_markets(q="Lakers", limit=5)
    assert len(results) >= 1
    r = results[0]

    assert isinstance(r, UnifiedMarketSearchResult)
    assert r.slug
    assert r.title
    assert r.platform in ("AlphaEdge", "Polymarket", "Kalshi")
    assert r.category
    assert r.market_type == "prediction"
    assert r.status in ("open", "locked", "resolved")


@pytest.mark.asyncio
async def test_search_limit_respected(db_session):
    """The limit parameter is respected."""
    await _seed_markets(db_session)
    svc = MarketService(db_session)

    results = await svc.search_markets(q=None, limit=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Static unit tests (no DB needed)
# ---------------------------------------------------------------------------


def test_platform_label_polymarket():
    assert MarketService._platform_label("polymarket") == "Polymarket"
    assert MarketService._platform_label("polymarket_mirror") == "Polymarket"


def test_platform_label_kalshi():
    assert MarketService._platform_label("kalshi") == "Kalshi"
    assert MarketService._platform_label("kalshi_mirror") == "Kalshi"


def test_platform_label_seed():
    assert MarketService._platform_label("seed") == "AlphaEdge"
    assert MarketService._platform_label("") == "AlphaEdge"
    assert MarketService._platform_label(None) == "AlphaEdge"


def test_status_rank_ordering():
    assert MarketService._status_rank("open") < MarketService._status_rank("locked")
    assert MarketService._status_rank("locked") < MarketService._status_rank("resolved")


def test_title_match_rank_exact_word():
    # "Lakers" starts a word in "Lakers vs Celtics"
    assert MarketService._title_match_rank("Lakers vs Celtics", "Lakers") == 0


def test_title_match_rank_partial():
    # "akers" is not a word boundary
    assert MarketService._title_match_rank("Lakers vs Celtics", "akers") == 1


def test_title_match_rank_empty_query():
    assert MarketService._title_match_rank("Anything", "") == 1


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def override_db(db_session):
    """Dependency override that injects the test db_session."""
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_search_endpoint_returns_200(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/search?q=Lakers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_search_endpoint_no_results(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/search?q=xyzzy_unmatchable_12345")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_endpoint_invalid_limit(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/search?limit=999")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_search_endpoint_empty_query_works(db_session, override_db):
    """No q param returns markets (up to limit)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/search?limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
