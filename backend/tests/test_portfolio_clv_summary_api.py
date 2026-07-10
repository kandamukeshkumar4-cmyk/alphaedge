"""K02 — GET /api/v1/portfolio/clv-summary (per-user realized CLV distribution).

Authed (JWT). Composes the caller's settled PaperOrder ledger with the resolved
closing line from CLVTrackingService and the canonical closing_line_value math.
401 anon; honest empty when the caller has no matching settled orders.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from app.db.models import PaperOrder, SignalEvent, User
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


async def _signup(client: AsyncClient, db_session, email: str) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "securepass1"}
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email.lower()))
    return token, user.id


def _resolved_signal(slug: str, closing_prob: float) -> SignalEvent:
    return SignalEvent(
        signal_type="forecast",
        platform="seed",
        market_id=slug,
        payload={
            "tracking": {
                "resolved": True,
                "market_slug": slug,
                "model_prob": 0.6,
                "closing_prob": closing_prob,
                "resolved_at": datetime.now(UTC).isoformat(),
            }
        },
    )


@pytest.mark.asyncio
async def test_clv_summary_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/portfolio/clv-summary")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_clv_summary_empty_is_honest(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, _ = await _signup(client, db_session, "clv-empty@example.com")
        r = await client.get(
            "/api/v1/portfolio/clv-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["mean"] is None
    assert body["positive_share"] is None
    assert body["total_clv"] == 0.0
    assert body["settled_orders"] == 0
    assert body["source"] == "none"
    assert [b["count"] for b in body["histogram"]] == [0, 0, 0, 0, 0, 0]
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_clv_summary_seeded_distribution(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user_id = await _signup(client, db_session, "clv-dist@example.com")

        # Resolved closing lines (YES implied) for two markets.
        db_session.add_all(
            [
                _resolved_signal(SLUG_A, closing_prob=0.70),
                _resolved_signal(SLUG_B, closing_prob=0.40),
            ]
        )
        await db_session.flush()

        # Caller's settled paper orders:
        #  A (YES @0.55): CLV = 0.70 - 0.55 = +0.15  -> positive, ">= 0.10" bin
        #  B (NO  @0.55): CLV = (1-0.40) - 0.55 = +0.05 -> "0.05..0.10" bin
        # Plus an UNSETTLED order that must be ignored.
        db_session.add_all(
            [
                PaperOrder(
                    user_id=user_id,
                    slug=SLUG_A,
                    side="YES",
                    outcome="yes",
                    shares=Decimal("10"),
                    price=Decimal("0.55"),
                    cost=Decimal("5.50"),
                    settled=True,
                    realized_pnl=Decimal("4.50"),
                ),
                PaperOrder(
                    user_id=user_id,
                    slug=SLUG_B,
                    side="NO",
                    outcome="no",
                    shares=Decimal("10"),
                    price=Decimal("0.55"),
                    cost=Decimal("5.50"),
                    settled=True,
                    realized_pnl=Decimal("1.00"),
                ),
                PaperOrder(
                    user_id=user_id,
                    slug=SLUG_A,
                    side="YES",
                    outcome="yes",
                    shares=Decimal("10"),
                    price=Decimal("0.50"),
                    cost=Decimal("5.00"),
                    settled=False,
                ),
            ]
        )
        await db_session.flush()

        r = await client.get(
            "/api/v1/portfolio/clv-summary",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["settled_orders"] == 2  # unsettled excluded
    assert body["matched_slugs"] == 2
    assert body["source"] == "paper_orders"
    assert body["mean"] == pytest.approx((0.15 + 0.05) / 2, abs=1e-6)
    assert body["positive_share"] == pytest.approx(1.0, abs=1e-6)
    assert body["total_clv"] == pytest.approx(0.20, abs=1e-6)

    bins = {b["label"]: b["count"] for b in body["histogram"]}
    assert bins[">= 0.10"] == 1
    assert bins["0.05..0.10"] == 1
    assert sum(bins.values()) == 2


@pytest.mark.asyncio
async def test_clv_summary_settled_without_closing_line_is_honest_empty(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user_id = await _signup(client, db_session, "clv-nomatch@example.com")
        # Settled order but NO resolved closing line for its slug -> honest empty.
        db_session.add(
            PaperOrder(
                user_id=user_id,
                slug="unmatched-slug",
                side="YES",
                outcome="yes",
                shares=Decimal("10"),
                price=Decimal("0.55"),
                cost=Decimal("5.50"),
                settled=True,
                realized_pnl=Decimal("1.00"),
            )
        )
        await db_session.flush()
        r = await client.get(
            "/api/v1/portfolio/clv-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["settled_orders"] == 1
    assert body["source"] == "paper_orders"
