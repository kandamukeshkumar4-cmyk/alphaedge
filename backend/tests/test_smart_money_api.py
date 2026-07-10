"""G07 — GET /api/v1/smart-money (fixture-seeded, read-only, no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, WalletPositionSnapshot
from app.db.session import get_db
from app.main import app

SLUG = "pm-will-lakers-beat-celtics"


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
async def test_smart_money_requires_slug():
    response = await _get("/api/v1/smart-money")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_smart_money_empty_market_is_honest():
    response = await _get("/api/v1/smart-money?slug=pm-nonexistent")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "pm-nonexistent"
    assert body["market_found"] is False
    assert body["paper_trading_only"] is True
    assert body["signal_only"] is True
    assert body["top_holders"]["wallet_count"] == 0
    assert body["top_holders"]["top_share"] == 0.0
    assert body["recent_large_flows"]["whale_count"] == 0
    assert body["recent_large_flows"]["deltas"] == []
    assert body["trade_intensity"]["fill_count"] == 0


@pytest.mark.asyncio
async def test_smart_money_composes_whale_fixtures(db_session):
    now = datetime.now(UTC)
    db_session.add(
        Market(
            slug=SLUG,
            title="Will the Lakers beat the Celtics?",
            question="Will the Lakers beat the Celtics?",
            category="NBA",
            status=MarketStatus.OPEN,
            source="polymarket",
            volume=100000,
        )
    )
    # Whale A: two snapshots with a +500 share add (a "large flow").
    db_session.add(
        WalletPositionSnapshot(
            wallet_address="0xwhaleAAAAAAAAAA",
            market_slug=SLUG,
            outcome="YES",
            size=Decimal("1000"),
            captured_at=now - timedelta(minutes=10),
        )
    )
    db_session.add(
        WalletPositionSnapshot(
            wallet_address="0xwhaleAAAAAAAAAA",
            market_slug=SLUG,
            outcome="YES",
            size=Decimal("1500"),
            captured_at=now - timedelta(minutes=1),
        )
    )
    # Two small holders for the concentration denominator (below the 100-share
    # whale threshold so they never show up as "large flows").
    for i, size in enumerate(("60", "90")):
        db_session.add(
            WalletPositionSnapshot(
                wallet_address=f"0xsmall{i}BBBBBBBB",
                market_slug=SLUG,
                outcome="YES",
                size=Decimal(size),
                captured_at=now - timedelta(minutes=2),
            )
        )
    await db_session.flush()

    response = await _get(f"/api/v1/smart-money?slug={SLUG}&top_n=1")
    assert response.status_code == 200
    body = response.json()

    assert body["market_found"] is True
    assert body["signal_only"] is True
    assert body["paper_trading_only"] is True

    # Top-holder summary: whale holds 1500 of 1650 total for top-1.
    top = body["top_holders"]
    assert top["wallet_count"] == 3
    assert top["top_n"] == 1
    assert top["top_share"] == pytest.approx(1500 / 1650, abs=1e-3)
    assert top["total_size"] == pytest.approx(1650.0)

    # Recent large flows: the +500 add is reported, wallet truncated.
    flows = body["recent_large_flows"]
    assert flows["whale_count"] == 1
    delta = flows["deltas"][0]
    assert delta["size_change"] == pytest.approx(500.0)
    assert delta["outcome"] == "YES"
    assert "0xwhale" in delta["wallet"]
    assert len(delta["wallet"]) < len("0xwhaleAAAAAAAAAA")  # never the full address

    # No fills seeded -> intensity is an honest zero, not fabricated.
    assert body["trade_intensity"]["fill_count"] == 0
    assert body["trade_intensity"]["notional"] == 0.0

    # Depth skew present (empty local book -> zero skew, no error).
    assert body["depth_skew"]["skew"] is not None


@pytest.mark.asyncio
async def test_smart_money_never_imports_order_path():
    """Read-only guardrail: the router module must not touch the order path."""
    import app.api.v1.smart_money as module

    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("OrderBookService", "RiskService", "OrderIntent"):
        assert forbidden not in source
