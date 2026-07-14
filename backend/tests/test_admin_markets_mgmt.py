"""Loop V23 A1 — admin market create/edit/pause/unpause/cancel."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import DomainEvent, Market, MarketStatus
from app.db.session import get_db
from app.main import app

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}
WRONG_HEADERS = {"X-Admin-API-Key": "wrong-key"}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _seed_open_market(db_session, slug: str = "admin-mgmt-mkt-1") -> Market:
    market = Market(
        slug=slug,
        title="Admin Mgmt Market",
        question="Will A1 land?",
        category="Sports",
        status=MarketStatus.OPEN,
    )
    db_session.add(market)
    await db_session.flush()
    return market


@pytest.mark.asyncio
async def test_create_market_requires_admin_key(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/markets",
            headers=WRONG_HEADERS,
            json={
                "slug": "new-admin-mkt",
                "title": "T",
                "question": "Q?",
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_market_success_and_audit(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/markets",
            headers=ADMIN_HEADERS,
            json={
                "slug": "admin-created-slug",
                "title": "Created Title",
                "question": "Will create work?",
                "category": "NBA",
                "description": "desc",
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "admin-created-slug"
    assert body["status"] == "open"
    assert body["paper_trading_only"] is True
    assert body["title"] == "Created Title"

    market = await db_session.scalar(
        select(Market).where(Market.slug == "admin-created-slug")
    )
    assert market is not None
    assert market.status == MarketStatus.OPEN

    events = (
        await db_session.scalars(
            select(DomainEvent).where(DomainEvent.event_type == "admin_market_created")
        )
    ).all()
    assert any(e.payload.get("slug") == "admin-created-slug" for e in events)


@pytest.mark.asyncio
async def test_create_market_duplicate_slug_409(db_session):
    await _seed_open_market(db_session, "dup-slug")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/markets",
            headers=ADMIN_HEADERS,
            json={"slug": "dup-slug", "title": "T", "question": "Q?"},
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_edit_market_updates_fields_and_audit(db_session):
    await _seed_open_market(db_session, "edit-me")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/admin/markets/edit-me",
            headers=ADMIN_HEADERS,
            json={"title": "Edited Title", "description": "new desc"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Edited Title"
    assert body["description"] == "new desc"

    events = (
        await db_session.scalars(
            select(DomainEvent).where(DomainEvent.event_type == "market_updated")
        )
    ).all()
    assert any(e.payload.get("slug") == "edit-me" for e in events)


@pytest.mark.asyncio
async def test_edit_resolved_market_rejected(db_session):
    market = await _seed_open_market(db_session, "resolved-edit")
    market.status = MarketStatus.RESOLVED
    await db_session.flush()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/admin/markets/resolved-edit",
            headers=ADMIN_HEADERS,
            json={"title": "Nope"},
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_pause_unpause_cancel_lifecycle_and_audits(db_session):
    await _seed_open_market(db_session, "lifecycle-mkt")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pause = await client.post(
            "/api/v1/admin/markets/lifecycle-mkt/pause", headers=ADMIN_HEADERS
        )
        assert pause.status_code == 200
        assert pause.json()["status"] == "locked"

        # already paused → 409
        pause_again = await client.post(
            "/api/v1/admin/markets/lifecycle-mkt/pause", headers=ADMIN_HEADERS
        )
        assert pause_again.status_code == 409

        unpause = await client.post(
            "/api/v1/admin/markets/lifecycle-mkt/unpause", headers=ADMIN_HEADERS
        )
        assert unpause.status_code == 200
        assert unpause.json()["status"] == "open"

        cancel = await client.post(
            "/api/v1/admin/markets/lifecycle-mkt/cancel", headers=ADMIN_HEADERS
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"
        assert cancel.json()["paper_trading_only"] is True

        # cancelled cannot unpause
        unpause_cancelled = await client.post(
            "/api/v1/admin/markets/lifecycle-mkt/unpause", headers=ADMIN_HEADERS
        )
        assert unpause_cancelled.status_code == 409

        # cancelled cannot cancel again
        cancel_again = await client.post(
            "/api/v1/admin/markets/lifecycle-mkt/cancel", headers=ADMIN_HEADERS
        )
        assert cancel_again.status_code == 409

    event_types = set(
        (
            await db_session.scalars(
                select(DomainEvent.event_type).where(
                    DomainEvent.event_type.in_(
                        ("market_paused", "market_unpaused", "market_cancelled")
                    )
                )
            )
        ).all()
    )
    assert "market_paused" in event_types
    assert "market_unpaused" in event_types
    assert "market_cancelled" in event_types


@pytest.mark.asyncio
async def test_pause_requires_admin_key(db_session):
    await _seed_open_market(db_session, "auth-pause")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/markets/auth-pause/pause", headers=WRONG_HEADERS
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cancel_unknown_market_404(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/markets/does-not-exist/cancel", headers=ADMIN_HEADERS
        )
    assert response.status_code == 404
