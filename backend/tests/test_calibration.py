from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, OrderOutcome, PaperOrder, User
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_calibration_latest_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_calibration_paper_trading_only_is_true():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_calibration_response_has_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "brier_score",
        "calibration_error",
        "markets_evaluated",
        "last_updated",
        "gate",
        "paper_trading_only",
    }


@pytest.mark.asyncio
async def test_calibration_no_resolved_markets_returns_no_data():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["gate"] == "no-data"
    assert body["markets_evaluated"] == 0


@pytest.mark.asyncio
async def test_calibration_ignores_resolved_market_without_winning_outcome(db_session):
    user = User(email="calibration@example.com", hashed_password="hash")
    market = Market(
        slug="calibration-missing-outcome",
        title="Calibration missing outcome",
        question="Will missing outcomes fail explicitly?",
        status=MarketStatus.RESOLVED,
        winning_outcome=None,
    )
    db_session.add_all([user, market])
    await db_session.flush()
    db_session.add(
        PaperOrder(
            user_id=user.id,
            slug=market.slug,
            side="YES",
            outcome="yes",
            shares=Decimal("1"),
            price=Decimal("0.5"),
            cost=Decimal("0.5"),
        )
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")

    assert response.status_code == 200
    assert response.json()["gate"] == "no-data"


@pytest.mark.asyncio
async def test_paper_orders_path_with_resolved_at_returns_200(db_session):
    """Regression (prod 500): a resolved market with a paper order and a
    populated resolved_at must not crash. The buckets in _from_paper_orders
    were tuples, so ``bucket[2] = resolved_at`` raised
    'tuple object does not support item assignment'. Both endpoints that fall
    through to _from_paper_orders must return 200."""
    from datetime import UTC, datetime

    user = User(email="paper-path@example.com", hashed_password="hash")
    market = Market(
        slug="calibration-paper-path",
        title="Calibration paper path",
        question="Does the paper-orders fallback survive resolved_at?",
        status=MarketStatus.RESOLVED,
        winning_outcome=OrderOutcome.YES,
        resolved_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    db_session.add_all([user, market])
    await db_session.flush()
    db_session.add(
        PaperOrder(
            user_id=user.id,
            slug=market.slug,
            side="YES",
            outcome="yes",
            shares=Decimal("1"),
            price=Decimal("0.7"),
            cost=Decimal("0.7"),
        )
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cal = await client.get("/api/v1/calibration/latest")
        track = await client.get("/api/v1/track-record")

    assert cal.status_code == 200
    assert cal.json()["markets_evaluated"] == 1
    assert track.status_code == 200
    assert track.json()["n"] == 1


def test_calibration_error_skips_nan_probability():
    """Defensive: Postgres NUMERIC 'NaN' reaching the binning math must not
    raise (int(nan*bins) -> ValueError). NaN samples are skipped."""
    from app.backtesting.metrics import brier_score, calibration_error

    preds = [0.6, float("nan"), 0.4]
    outs = [1, 1, 0]
    assert calibration_error(preds, outs) >= 0.0
    assert brier_score([0.6, 0.4], [1, 0]) >= 0.0


def test_track_record_calibration_bins_skip_nan():
    """Defensive: track-record calibration binning must not 500 on a NaN
    probability."""
    from app.api.v1.track_record import _calibration_bins

    bins = _calibration_bins([0.6, float("nan"), 0.4], [1, 1, 0])
    assert len(bins) == 10
    assert sum(b.count for b in bins) == 2
