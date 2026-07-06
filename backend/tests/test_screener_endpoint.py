"""O03: screener service + endpoint over seeded odds snapshots."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.models import Market, OddsSnapshot, SignalEvent
from app.db.session import get_db
from app.main import app
from app.services.signals_service import SignalsService

NOW = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


def _snap(slug: str, implied: str, minutes_ago: int, source: str = "polymarket.gamma") -> OddsSnapshot:
    return OddsSnapshot(
        market_slug=slug,
        implied_yes=Decimal(implied),
        source=source,
        captured_at=NOW - timedelta(minutes=minutes_ago),
    )


async def _seed(db_session):
    # Momentum market: clean upward drift 0.30 → 0.48
    db_session.add_all(
        [
            _snap("mom-mkt", "0.30", 40),
            _snap("mom-mkt", "0.36", 30),
            _snap("mom-mkt", "0.42", 20),
            _snap("mom-mkt", "0.48", 10),
        ]
    )
    # Expiry-fade market: longshot at 0.06 closing in 6h
    db_session.add(_snap("fade-mkt", "0.06", 5))
    db_session.add(
        Market(
            slug="fade-mkt",
            title="Fade Market",
            question="Will the longshot hit?",
            lock_at=NOW + timedelta(hours=6),
        )
    )
    # Quiet market: flat, should NOT produce a hit
    db_session.add_all(
        [
            _snap("flat-mkt", "0.50", 30),
            _snap("flat-mkt", "0.50", 20),
            _snap("flat-mkt", "0.50", 10),
        ]
    )
    await db_session.flush()


async def test_screeners_find_momentum_and_expiry_fade_and_persist(db_session):
    await _seed(db_session)
    result = await SignalsService(db_session).screeners(now=NOW)

    kinds = {(h["kind"], h["market_slug"]) for h in result["hits"]}
    assert ("momentum", "mom-mkt") in kinds
    assert ("expiry_fade", "fade-mkt") in kinds
    assert not any(h["market_slug"] == "flat-mkt" for h in result["hits"])
    assert result["paper_trading_only"] is True

    mom = next(h for h in result["hits"] if h["kind"] == "momentum")
    assert mom["direction"] == "up"

    persisted = (
        await db_session.execute(
            select(SignalEvent.signal_type).where(SignalEvent.signal_type.like("screener:%"))
        )
    ).scalars().all()
    assert "screener:momentum" in persisted
    assert "screener:expiry_fade" in persisted


async def test_screeners_screen_filter_limits_kind(db_session):
    await _seed(db_session)
    result = await SignalsService(db_session).screeners(screen="momentum", now=NOW, persist=False)
    assert result["hits"]
    assert all(h["kind"] == "momentum" for h in result["hits"])


async def test_screener_endpoint_returns_200_and_shape(db_session):
    # The route uses real wall-clock for its lookback, so seed a fresh
    # momentum series relative to now (not the fixed NOW fixture date).
    real_now = datetime.now(timezone.utc)
    for minutes, implied in ((40, "0.30"), (30, "0.36"), (20, "0.42"), (10, "0.48")):
        db_session.add(
            OddsSnapshot(
                market_slug="live-mom-mkt",
                implied_yes=Decimal(implied),
                source="polymarket.gamma",
                captured_at=real_now - timedelta(minutes=minutes),
            )
        )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/screeners")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["paper_trading_only"] is True
    assert "hits" in body and isinstance(body["hits"], list)
    assert any(h["market_slug"] == "live-mom-mkt" for h in body["hits"])


async def test_screener_endpoint_rejects_bad_screen(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/screeners", params={"screen": "bogus"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


async def test_screeners_ignore_snapshots_outside_lookback(db_session):
    # A clean upward drift, but every reading is 10 days old — outside the
    # default 168h lookback, so it must NOT produce a momentum hit.
    db_session.add_all(
        [
            _snap("stale-mkt", "0.30", 60 * 24 * 10 + 40),
            _snap("stale-mkt", "0.40", 60 * 24 * 10 + 30),
            _snap("stale-mkt", "0.50", 60 * 24 * 10 + 20),
        ]
    )
    await db_session.flush()
    result = await SignalsService(db_session).screeners(now=NOW, persist=False)
    assert not any(h["market_slug"] == "stale-mkt" for h in result["hits"])


async def test_screeners_empty_when_no_snapshots(db_session):
    result = await SignalsService(db_session).screeners(now=NOW)
    assert result["count"] == 0
    assert result["hits"] == []
    persisted = (
        await db_session.execute(select(func.count()).select_from(SignalEvent))
    ).scalar_one()
    assert persisted == 0
