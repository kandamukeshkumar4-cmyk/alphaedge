"""N02 — Forecast drivers tests (Loop V9).

``GET /api/v1/markets/{slug}/drivers`` — PUBLIC GET. Top drivers behind the model
probability: the model-vs-market gap + recent alert-family signals (family +
citation). Unknown slug → honest {found:false}; known market with no drivers →
{found:true, drivers:[]}. Never a 404, never fabricated data.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    Market,
    MarketStatus,
    OddsSnapshot,
    PredictionLog,
    SignalEvent,
)
from app.db.session import get_db
from app.main import app

SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


async def _seed_market(db_session, slug: str, *, yes_price: float | None) -> None:
    db_session.add(
        Market(
            slug=slug, title="Lakers vs Celtics", question="LAL win?",
            status=MarketStatus.OPEN, volume=5000,
        )
    )
    await db_session.flush()
    if yes_price is not None:
        db_session.add(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=Decimal(str(yes_price)),
                source="seed",
                captured_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_known_slug_with_signals(db_session):
    await _seed_market(db_session, SLUG, yes_price=0.50)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PredictionLog(
                market_slug=SLUG,
                predicted_prob=Decimal("0.62"),
                confidence=Decimal("0.7"),
                predicted_at=now - timedelta(hours=1),
            ),
            SignalEvent(
                signal_type="news:mispricing",
                platform="seed",
                market_id=SLUG,
                payload={
                    "id": "sig-1",
                    "news_url": "https://example.com/n1",
                    "headline": "Star player questionable",
                    "model_p": 0.62,
                    "market_p": 0.50,
                },
                headline_eligible=True,
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    await db_session.flush()

    r = await _get(f"/api/v1/markets/{SLUG}/drivers")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["model_p"] == 0.62
    assert body["market_p"] == 0.50
    assert body["gap"] == 0.12
    labels = [d["label"] for d in body["drivers"]]
    # gap driver first, then the news signal driver (by headline).
    assert labels[0] == "Model vs market gap"
    assert body["drivers"][0]["direction"] == "favors YES"
    assert body["drivers"][0]["family"] is None
    signal_driver = body["drivers"][1]
    assert signal_driver["label"] == "Star player questionable"
    assert signal_driver["family"] == "news:mispricing"
    assert signal_driver["direction"] == "favors YES"
    assert signal_driver["citation"]["news_url"] == "https://example.com/n1"


@pytest.mark.asyncio
async def test_unknown_slug_honest(db_session):
    r = await _get("/api/v1/markets/does-not-exist/drivers")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False
    assert body["model_p"] is None
    assert body["market_p"] is None
    assert body["gap"] is None
    assert body["drivers"] == []


@pytest.mark.asyncio
async def test_known_slug_no_drivers_honest(db_session):
    # Known market, no model prediction and no odds snapshot, no signals.
    await _seed_market(db_session, SLUG, yes_price=None)
    r = await _get(f"/api/v1/markets/{SLUG}/drivers")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["model_p"] is None
    assert body["gap"] is None
    assert body["drivers"] == []
