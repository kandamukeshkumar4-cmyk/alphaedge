"""Loop 105: GET /api/v1/markets pagination (limit/offset + X-Total-Count headers)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus
from app.db.session import get_db
from app.main import app


async def _seed_n_markets(db_session, n: int, *, category: str = "Sports", prefix: str = "pag") -> None:
    db_session.add_all(
        [
            Market(
                slug=f"{prefix}-{i:04d}",
                title=f"Pagination Market {i:04d}",
                question=f"Will market {i:04d} resolve YES?",
                category=category,
                volume=n - i,
                traders=i,
                status=MarketStatus.OPEN,
            )
            for i in range(n)
        ]
    )
    await db_session.flush()


@pytest.fixture
def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_default_limit_is_100_not_full_catalog(db_session, client):
    await _seed_n_markets(db_session, 150)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 100
    assert response.headers["X-Total-Count"] == "150"
    assert response.headers["X-Page-Limit"] == "100"
    assert response.headers["X-Page-Offset"] == "0"


@pytest.mark.asyncio
async def test_limit_and_offset_slice_correctly(db_session, client):
    await _seed_n_markets(db_session, 30)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        page1 = await ac.get("/api/v1/markets", params={"limit": 10, "offset": 0, "sort": "volume"})
        page2 = await ac.get("/api/v1/markets", params={"limit": 10, "offset": 10, "sort": "volume"})
    assert page1.status_code == 200
    assert page2.status_code == 200
    slugs1 = [m["slug"] for m in page1.json()]
    slugs2 = [m["slug"] for m in page2.json()]
    assert len(slugs1) == 10
    assert len(slugs2) == 10
    assert set(slugs1).isdisjoint(set(slugs2))
    # volume desc: pag-0000 has volume 30, pag-0001 has 29, ...
    assert slugs1[0] == "pag-0000"
    assert slugs2[0] == "pag-0010"


@pytest.mark.asyncio
async def test_total_count_header_reflects_full_match_not_page(db_session, client):
    await _seed_n_markets(db_session, 40)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    assert len(response.json()) == 5
    assert response.headers["X-Total-Count"] == "40"
    assert response.headers["X-Page-Limit"] == "5"
    assert response.headers["X-Page-Offset"] == "0"


@pytest.mark.asyncio
async def test_limit_over_500_returns_400(db_session, client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets", params={"limit": 501})
    assert response.status_code == 400
    assert "limit" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_limit_zero_or_negative_returns_400(db_session, client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        zero = await ac.get("/api/v1/markets", params={"limit": 0})
        neg = await ac.get("/api/v1/markets", params={"limit": -1})
    assert zero.status_code == 400
    assert neg.status_code == 400


@pytest.mark.asyncio
async def test_negative_offset_returns_400(db_session, client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets", params={"offset": -1})
    assert response.status_code == 400
    assert "offset" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cache_key_distinguishes_pages(db_session, client):
    await _seed_n_markets(db_session, 25)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        page1 = await ac.get("/api/v1/markets", params={"limit": 5, "offset": 0, "sort": "volume"})
        page2 = await ac.get("/api/v1/markets", params={"limit": 5, "offset": 5, "sort": "volume"})
        page1_again = await ac.get(
            "/api/v1/markets", params={"limit": 5, "offset": 0, "sort": "volume"}
        )
    assert page1.status_code == 200
    assert page2.status_code == 200
    slugs1 = [m["slug"] for m in page1.json()]
    slugs2 = [m["slug"] for m in page2.json()]
    slugs1b = [m["slug"] for m in page1_again.json()]
    assert slugs1 != slugs2
    assert set(slugs1).isdisjoint(set(slugs2))
    assert slugs1 == slugs1b  # cache hit must still be page 1


@pytest.mark.asyncio
async def test_category_and_sort_filters_still_apply_with_pagination(db_session, client):
    await _seed_n_markets(db_session, 15, category="Crypto", prefix="cry")
    await _seed_n_markets(db_session, 15, category="Culture", prefix="cul")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/markets",
            params={"category": "crypto", "sort": "volume", "limit": 5, "offset": 0},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    assert all(m["category"] == "Crypto" for m in body)
    assert response.headers["X-Total-Count"] == "15"
    assert body[0]["slug"] == "cry-0000"  # highest volume among crypto


@pytest.mark.asyncio
async def test_offset_past_end_returns_empty_list_not_error(db_session, client):
    await _seed_n_markets(db_session, 10)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets", params={"limit": 10, "offset": 100})
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "10"
    assert response.headers["X-Page-Limit"] == "10"
    assert response.headers["X-Page-Offset"] == "100"


@pytest.mark.asyncio
async def test_sort_ties_are_stable_across_page_boundary(db_session, client):
    """Equal volume keys must not duplicate/drop rows across LIMIT/OFFSET pages.

    Seeds >=4 markets with at least 3 sharing an identical volume that straddles
    a limit=2 page boundary. Union of pages must equal the full id set.
    """
    # Four markets: three share volume=100 (tie straddles pages), one unique.
    specs = [
        ("tie-a", 100),
        ("tie-b", 100),
        ("tie-c", 100),
        ("unique-hi", 200),
    ]
    db_session.add_all(
        [
            Market(
                slug=slug,
                title=f"Tie market {slug}",
                question="?",
                category="Sports",
                volume=volume,
                traders=0,
                status=MarketStatus.OPEN,
            )
            for slug, volume in specs
        ]
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        full = await ac.get("/api/v1/markets", params={"limit": 50, "offset": 0, "sort": "volume"})
        page1 = await ac.get("/api/v1/markets", params={"limit": 2, "offset": 0, "sort": "volume"})
        page2 = await ac.get("/api/v1/markets", params={"limit": 2, "offset": 2, "sort": "volume"})

    assert full.status_code == 200
    assert page1.status_code == 200
    assert page2.status_code == 200
    full_ids = [m["id"] for m in full.json()]
    p1_ids = [m["id"] for m in page1.json()]
    p2_ids = [m["id"] for m in page2.json()]
    assert len(full_ids) == 4
    assert len(p1_ids) == 2
    assert len(p2_ids) == 2
    assert set(p1_ids).isdisjoint(set(p2_ids))
    assert set(p1_ids) | set(p2_ids) == set(full_ids)
    # Round-trip: paging must not invent or drop any id from the full set.
    assert sorted(p1_ids + p2_ids) == sorted(full_ids)
