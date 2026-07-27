"""Tests for scanner convergence endpoint."""
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
import pytest

from app.db.models import Scanner, ScannerRun, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Never leak the get_db override into sibling test modules."""
    yield
    app.dependency_overrides.pop(get_db, None)


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_data(db_session):
    svc = MarketService(db_session)
    await svc.create_market(slug="market-1", title="Market 1", question="?", volume=100)
    await svc.create_market(slug="market-2", title="Market 2", question="?", volume=200)

    user = User(email="test@example.com", hashed_password="pw")
    db_session.add(user)
    await db_session.flush()

    user_id = str(user.id)

    s1 = Scanner(name="S1", owner=user_id, is_public=True, status="active", spec={})
    s2 = Scanner(name="S2", owner=user_id, is_public=True, status="active", spec={})
    s3 = Scanner(name="S3", owner=user_id, is_public=True, status="active", spec={})
    db_session.add_all([s1, s2, s3])
    await db_session.flush()

    now = datetime.now(UTC)
    r1 = ScannerRun(
        scanner_id=s1.id,
        status="completed",
        started_at=now,
        result={"candidates": [{"market_slug": "market-1"}, {"market_slug": "market-2"}]},
    )
    r2 = ScannerRun(
        scanner_id=s2.id,
        status="completed",
        started_at=now,
        result={"candidates": [{"market_slug": "market-1"}]},
    )
    r3 = ScannerRun(
        scanner_id=s3.id,
        status="completed",
        started_at=now,
        result={"candidates": []},
    )
    db_session.add_all([r1, r2, r3])
    await db_session.flush()

    return user, s1, s2, s3


@pytest.mark.asyncio
async def test_convergence_counts_market_in_two_scanners(db_session):
    await _seed_data(db_session)
    client = await _client_for(db_session)

    res = await client.get("/api/v1/scanners/convergence?scope=public&min_scanners=2")
    assert res.status_code == 200
    data = res.json()
    
    assert data["scanner_total"] == 3
    items = data["items"]
    assert len(items) == 1
    assert items[0]["market_slug"] == "market-1"
    assert items[0]["scanner_count"] == 2
    assert len(items[0]["scanners"]) == 2


@pytest.mark.asyncio
async def test_convergence_excludes_single_scanner_markets(db_session):
    await _seed_data(db_session)
    client = await _client_for(db_session)

    res = await client.get("/api/v1/scanners/convergence?scope=public&min_scanners=2")
    assert res.status_code == 200
    items = res.json()["items"]
    slugs = [it["market_slug"] for it in items]
    assert "market-2" not in slugs


@pytest.mark.asyncio
async def test_convergence_scope_mine_requires_auth(db_session):
    await _seed_data(db_session)
    client = await _client_for(db_session)

    res = await client.get("/api/v1/scanners/convergence?scope=mine&min_scanners=2")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_convergence_uses_latest_run_only(db_session):
    user, s1, s2, s3 = await _seed_data(db_session)

    r_old = ScannerRun(
        scanner_id=s2.id,
        status="completed",
        started_at=datetime.now(UTC) - timedelta(hours=1),
        result={"candidates": [{"market_slug": "market-2"}]},
    )
    db_session.add(r_old)
    await db_session.flush()

    client = await _client_for(db_session)
    res = await client.get("/api/v1/scanners/convergence?scope=public&min_scanners=2")
    assert res.status_code == 200
    items = res.json()["items"]
    
    slugs = [it["market_slug"] for it in items]
    assert "market-2" not in slugs
