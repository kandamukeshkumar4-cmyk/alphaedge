"""H01 — GET /api/v1/desk (fixture-seeded, read-only, no network).

The desk aggregate composes the market snapshot, latest model edge, G07
smart-money summary, G02 arb match and latest signals into ONE response.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    Market,
    MarketStatus,
    PredictionLog,
    SignalEvent,
    VenueMarketMatch,
    WalletPositionSnapshot,
)
from app.db.session import get_db
from app.main import app

SLUG = "pm-will-lakers-beat-celtics"
KS_SLUG = "ks-kxnba-lalbos-26jan15"


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


@pytest.mark.asyncio
async def test_desk_requires_slug():
    response = await _get("/api/v1/desk")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_desk_unknown_slug_is_honest():
    response = await _get("/api/v1/desk?slug=pm-nonexistent")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "pm-nonexistent"
    assert body["market_found"] is False
    assert body["paper_trading_only"] is True
    assert body["signal_only"] is True
    assert body["market"] is None
    assert body["book"] is None
    assert body["edge"] is None
    assert body["arb"] is None
    assert body["signals"] == []
    # Smart-money section is present but honestly empty.
    assert body["smart_money"]["market_found"] is False
    assert body["smart_money"]["top_holders"]["wallet_count"] == 0


@pytest.mark.asyncio
async def test_desk_composes_all_sections(db_session):
    now = datetime.now(UTC)
    market = Market(
        slug=SLUG,
        title="Will the Lakers beat the Celtics?",
        question="Will the Lakers beat the Celtics?",
        category="NBA",
        status=MarketStatus.OPEN,
        source="polymarket",
        volume=100000,
    )
    db_session.add(market)
    await db_session.flush()

    # Latest model edge.
    db_session.add(
        PredictionLog(
            market_id=market.id,
            market_slug=SLUG,
            predicted_prob=Decimal("0.62"),
            confidence=Decimal("0.70"),
            input_feature_hash="feat-abc",
            predicted_at=now - timedelta(minutes=5),
        )
    )
    # Smart-money input: one whale holder.
    db_session.add(
        WalletPositionSnapshot(
            wallet_address="0xwhaleAAAAAAAAAA",
            market_slug=SLUG,
            outcome="YES",
            size=Decimal("1500"),
            captured_at=now - timedelta(minutes=1),
        )
    )
    # Cross-venue arb match touching this slug.
    db_session.add(
        VenueMarketMatch(
            pm_slug=SLUG,
            ks_slug=KS_SLUG,
            pm_title="Lakers beat Celtics",
            ks_title="LAL def BOS",
            confidence=0.9,
            reasons=["title", "date"],
            stale=False,
        )
    )
    # A signal event for the slug.
    db_session.add(
        SignalEvent(
            signal_type="news:mispricing",
            platform="polymarket",
            market_id=SLUG,
            headline_eligible=True,
            payload={"model_p": 0.62, "market_p": 0.5, "gap": 0.12},
        )
    )
    await db_session.flush()

    response = await _get(f"/api/v1/desk?slug={SLUG}&top_n=1")
    assert response.status_code == 200
    body = response.json()

    assert body["market_found"] is True
    assert body["signal_only"] is True
    assert body["market"]["slug"] == SLUG

    # Edge from the latest PredictionLog.
    assert body["edge"]["predicted_prob"] == pytest.approx(0.62)
    assert body["edge"]["source"] == "prediction_log"

    # Smart-money summary reused verbatim from G07.
    assert body["smart_money"]["market_found"] is True
    assert body["smart_money"]["top_holders"]["wallet_count"] == 1

    # Arb match surfaced.
    assert body["arb"]["ks_slug"] == KS_SLUG
    assert body["arb"]["confidence"] == pytest.approx(0.9)
    assert body["arb"]["stale"] is False

    # Latest signals for the slug.
    assert len(body["signals"]) == 1
    assert body["signals"][0]["signal_type"] == "news:mispricing"


@pytest.mark.asyncio
async def test_desk_never_imports_order_path():
    """Read-only guardrail: the router module must not touch the order path."""
    import app.api.v1.desk as module

    source = open(module.__file__, encoding="utf-8").read()
    # OrderBookService is used only for a read-only L2 book fetch; the risk /
    # intent / submit write path must never appear on this surface.
    assert "RiskService" not in source
    assert "OrderIntent" not in source
    # submit_order (the write path) must never be called from the desk surface.
    assert "submit_order" not in source
