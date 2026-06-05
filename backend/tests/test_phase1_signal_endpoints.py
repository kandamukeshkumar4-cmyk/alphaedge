from datetime import UTC, datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.models import OddsSnapshot, SignalEvent
from app.db.session import get_db
from app.main import app


CAPTURED_AT = datetime(2026, 1, 14, 18, tzinfo=UTC)
CLOSE_AT = datetime(2026, 1, 15, 0, 30, tzinfo=UTC)


async def test_arbitrage_endpoint_returns_net_signal_and_persists_event(db_session):
    db_session.add_all(
        [
            _snapshot(
                source="polymarket.gamma",
                platform_market_id="poly-lal-bos",
                price=Decimal("0.42"),
                outcome_name="Yes",
            ),
            _snapshot(
                source="kalshi.rest",
                platform_market_id="kalshi-lal-bos",
                price=Decimal("0.46"),
                outcome_name="Yes",
            ),
        ]
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals/arbitrage",
                params={"platform": "polymarket", "market_id": "poly-lal-bos"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["paper_trading_only"] is True
    assert body["signal"]["is_arbitrage"] is True
    assert body["signal"]["headline_eligible"] is True
    assert body["signal"]["gross_cost"] == 0.96
    assert body["signal"]["net_cost"] == 0.98
    assert body["signal"]["net_spread"] == 0.02
    assert body["signal"]["resolution_status"] == "confirmed"
    assert "No execution" in body["disclaimer"]

    stored_count = await db_session.scalar(select(func.count()).select_from(SignalEvent))
    stored = await db_session.scalar(select(SignalEvent))
    assert stored_count == 1
    assert stored is not None
    assert stored.signal_type == "arbitrage"
    assert stored.platform == "polymarket"
    assert stored.market_id == "poly-lal-bos"
    assert stored.headline_eligible is True
    assert stored.payload["signal"]["net_spread"] == 0.02


async def test_arbitrage_endpoint_labels_unconfirmed_pair_without_persisting_headline(
    db_session,
):
    db_session.add_all(
        [
            _snapshot(
                source="polymarket.gamma",
                platform_market_id="poly-lal-bos",
                price=Decimal("0.42"),
                outcome_name="Yes",
            ),
            _snapshot(
                source="kalshi.rest",
                platform_market_id="kalshi-gsw-bos",
                event_id="nba-gsw-bos-2026-01-15",
                entities=("golden-state-warriors", "boston-celtics"),
                price=Decimal("0.46"),
                outcome_name="Yes",
            ),
        ]
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals/arbitrage",
                params={"platform": "polymarket", "market_id": "poly-lal-bos"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["is_arbitrage"] is False
    assert body["signal"]["headline_eligible"] is False
    assert body["signal"]["resolution_status"] == "unconfirmed"
    assert "entity_mismatch" in body["signal"]["match_reasons"]
    stored_count = await db_session.scalar(select(func.count()).select_from(SignalEvent))
    assert stored_count == 0


async def test_arbitrage_endpoint_prefers_confirmed_resolution_match(db_session):
    db_session.add_all(
        [
            _snapshot(
                source="polymarket.gamma",
                platform_market_id="poly-lal-bos",
                price=Decimal("0.42"),
                outcome_name="Yes",
            ),
            _snapshot(
                source="kalshi.rest",
                platform_market_id="kalshi-gsw-bos",
                event_id="nba-gsw-bos-2026-01-15",
                entities=("golden-state-warriors", "boston-celtics"),
                price=Decimal("0.46"),
                outcome_name="Yes",
                captured_at=datetime(2026, 1, 14, 18, 5, tzinfo=UTC),
            ),
            _snapshot(
                source="kalshi.rest",
                platform_market_id="kalshi-lal-bos",
                price=Decimal("0.46"),
                outcome_name="Yes",
                captured_at=CAPTURED_AT,
            ),
        ]
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals/arbitrage",
                params={"platform": "polymarket", "market_id": "poly-lal-bos"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["resolution_status"] == "confirmed"
    assert body["signal"]["no_leg"]["market"]["market_id"] == "kalshi-lal-bos"
    assert body["signal"]["headline_eligible"] is True


async def test_arbitrage_endpoint_rejects_platform_wildcards(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals/arbitrage",
                params={"platform": "%", "market_id": "poly-lal-bos"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid platform"


async def test_dutching_endpoint_returns_equalized_risk_free_signal_and_persists_event(
    db_session,
):
    db_session.add_all(
        [
            _snapshot(
                source="polymarket.gamma",
                platform_market_id="poly-three-way",
                price=Decimal("0.30"),
                outcome_name="Lakers",
                market_type="multi_outcome",
                exhaustive=True,
                mutually_exclusive=True,
            ),
            _snapshot(
                source="polymarket.gamma",
                platform_market_id="poly-three-way",
                price=Decimal("0.25"),
                outcome_name="Celtics",
                market_type="multi_outcome",
                exhaustive=True,
                mutually_exclusive=True,
            ),
            _snapshot(
                source="polymarket.gamma",
                platform_market_id="poly-three-way",
                price=Decimal("0.20"),
                outcome_name="Draw",
                market_type="multi_outcome",
                exhaustive=True,
                mutually_exclusive=True,
            ),
        ]
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals/dutching",
                params={"platform": "polymarket", "market_id": "poly-three-way"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["risk_free"] is True
    assert body["signal"]["coverage_status"] == "confirmed"
    assert body["signal"]["total_cost"] == 0.75
    assert body["signal"]["profit"] == 0.25
    assert {leg["outcome"]: leg["quantity"] for leg in body["signal"]["legs"]} == {
        "Lakers": 1.0,
        "Celtics": 1.0,
        "Draw": 1.0,
    }

    stored_count = await db_session.scalar(select(func.count()).select_from(SignalEvent))
    stored = await db_session.scalar(select(SignalEvent))
    assert stored_count == 1
    assert stored is not None
    assert stored.signal_type == "dutching"
    assert stored.payload["signal"]["profit"] == 0.25


def _snapshot(
    *,
    source: str,
    platform_market_id: str,
    price: Decimal,
    outcome_name: str,
    event_id: str = "nba-lal-bos-2026-01-15",
    entities: tuple[str, ...] = ("los-angeles-lakers", "boston-celtics"),
    market_type: str = "binary",
    exhaustive: bool = True,
    mutually_exclusive: bool = True,
    captured_at: datetime = CAPTURED_AT,
) -> OddsSnapshot:
    return OddsSnapshot(
        market_slug=f"{source}:{platform_market_id}:{outcome_name.lower()}",
        implied_yes=price,
        price=price,
        source=source,
        book=source,
        event_id=event_id,
        platform_market_id=platform_market_id,
        title="Will the Lakers beat the Celtics?",
        market_type=market_type,
        outcome_name=outcome_name,
        close_at=CLOSE_AT,
        captured_at=captured_at,
        snapshot_metadata={
            "normalized_entities": list(entities),
            "resolution_source": "nba-final-score",
            "resolution_rules": "YES resolves from the official NBA final score.",
            "exhaustive": exhaustive,
            "mutually_exclusive": mutually_exclusive,
        },
    )
