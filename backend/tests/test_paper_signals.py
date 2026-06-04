from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


@pytest.mark.asyncio
async def test_market_signal_summary_starts_empty_and_includes_binary_outcomes(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-signal-summary-market",
        title="Signal summary market",
        question="Will the signal summary include both outcomes?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/markets/{market.slug}/signals")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_trading_only"] is True
    assert payload["market_slug"] == market.slug
    assert payload["selected_outcome"] is None
    assert payload["total_signals"] == 0
    assert payload["options"] == [
        {"outcome": "yes", "count": 0, "percentage": 0.0},
        {"outcome": "no", "count": 0, "percentage": 0.0},
    ]


@pytest.mark.asyncio
async def test_submit_market_signal_records_one_active_signal_per_account(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-signal-submit-market",
        title="Signal submit market",
        question="Will one account update rather than duplicate a signal?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account = await market_service.seed_system_account(
        UUID("00000000-0000-0000-0000-000000000001"),
        Decimal("100000"),
        "System Paper Account",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first = await client.post(
                f"/api/v1/markets/{market.slug}/signals",
                json={"account_id": str(account.id), "outcome": "yes"},
            )
            second = await client.post(
                f"/api/v1/markets/{market.slug}/signals",
                json={"account_id": str(account.id), "outcome": "no"},
            )
            summary = await client.get(
                f"/api/v1/markets/{market.slug}/signals",
                params={"account_id": str(account.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert first.json()["selected_outcome"] == "yes"
    assert first.json()["total_signals"] == 1
    assert first.json()["options"] == [
        {"outcome": "yes", "count": 1, "percentage": 100.0},
        {"outcome": "no", "count": 0, "percentage": 0.0},
    ]

    assert second.status_code == 200
    assert second.json()["selected_outcome"] == "no"
    assert second.json()["total_signals"] == 1
    assert second.json()["options"] == [
        {"outcome": "yes", "count": 0, "percentage": 0.0},
        {"outcome": "no", "count": 1, "percentage": 100.0},
    ]

    assert summary.status_code == 200
    assert summary.json()["selected_outcome"] == "no"
    assert summary.json()["total_signals"] == 1


@pytest.mark.asyncio
async def test_market_signal_summary_uses_paper_account_token_context(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-token-signal-market",
        title="Token signal market",
        question="Will signal summaries stay scoped to the browser account?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    headers_a = {"X-Paper-Account-Token": "11111111-1111-4111-8111-111111111111"}
    headers_b = {"X-Paper-Account-Token": "22222222-2222-4222-8222-222222222222"}

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            account_a = await client.get("/api/v1/paper-account", headers=headers_a)
            submit_a = await client.post(
                f"/api/v1/markets/{market.slug}/signals",
                headers=headers_a,
                json={"account_id": account_a.json()["id"], "outcome": "yes"},
            )
            summary_a = await client.get(
                f"/api/v1/markets/{market.slug}/signals",
                headers=headers_a,
            )
            summary_b = await client.get(
                f"/api/v1/markets/{market.slug}/signals",
                headers=headers_b,
            )
    finally:
        app.dependency_overrides.clear()

    assert account_a.status_code == 200
    assert submit_a.status_code == 200
    assert summary_a.status_code == 200
    assert summary_a.json()["selected_outcome"] == "yes"
    assert summary_a.json()["total_signals"] == 1
    assert summary_b.status_code == 200
    assert summary_b.json()["selected_outcome"] is None
    assert summary_b.json()["total_signals"] == 1
