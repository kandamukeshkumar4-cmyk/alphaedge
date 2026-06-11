from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.db.models import Evaluation, Market, OddsSnapshot, OrderOutcome, PredictionLog
from app.eval.service import EvalService


@pytest.mark.asyncio
async def test_compute_aggregates_uses_weighted_calibration_error(db_session):
    markets = [
        Market(
            slug=f"eval-calibration-{index}",
            title=f"Calibration market {index}",
            question="Will the calibration fixture resolve YES?",
        )
        for index in range(4)
    ]
    db_session.add_all(markets)
    await db_session.flush()

    db_session.add_all(
        [
            Evaluation(
                market_id=markets[0].id,
                brier_score=Decimal("0.010000"),
                predicted_prob=Decimal("0.1000"),
                actual_outcome=0,
            ),
            Evaluation(
                market_id=markets[1].id,
                brier_score=Decimal("0.640000"),
                predicted_prob=Decimal("0.2000"),
                actual_outcome=1,
            ),
            Evaluation(
                market_id=markets[2].id,
                brier_score=Decimal("0.040000"),
                predicted_prob=Decimal("0.8000"),
                actual_outcome=1,
            ),
            Evaluation(
                market_id=markets[3].id,
                brier_score=Decimal("0.010000"),
                predicted_prob=Decimal("0.9000"),
                actual_outcome=1,
            ),
        ]
    )
    await db_session.flush()

    aggregate = await EvalService(db_session).compute_aggregates()

    assert aggregate.market_count == 4
    assert float(aggregate.mean_brier) == pytest.approx(0.175)
    assert float(aggregate.calibration_error) == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_evaluate_market_uses_latest_pre_close_odds_snapshot_for_closing_implied(
    db_session,
):
    close_at = datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc)
    market = Market(
        slug="eval-lakers-celtics",
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=close_at,
        winning_outcome=OrderOutcome.YES,
    )
    db_session.add(market)
    await db_session.flush()

    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal("0.6000"),
                source="fixture",
                captured_at=datetime(2026, 1, 14, 22, 0, tzinfo=timezone.utc),
                close_at=close_at,
            ),
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal("0.6400"),
                source="fixture",
                captured_at=datetime(2026, 1, 15, 0, 25, tzinfo=timezone.utc),
                close_at=close_at,
            ),
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal("0.9900"),
                source="fixture",
                captured_at=datetime(2026, 1, 15, 0, 35, tzinfo=timezone.utc),
                close_at=close_at,
            ),
        ]
    )
    db_session.add(
        PredictionLog(
            market_id=market.id,
            market_slug=market.slug,
            predicted_prob=Decimal("0.7200"),
        )
    )
    await db_session.flush()

    evaluation = await EvalService(db_session).evaluate_market(market.id)

    assert float(evaluation.brier_score) == pytest.approx(0.0784)
    assert float(evaluation.predicted_prob) == pytest.approx(0.72)
    assert float(evaluation.closing_implied) == pytest.approx(0.64)


@pytest.mark.asyncio
async def test_evaluations_endpoint_applies_bounded_limit(db_session):
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app

    markets = [
        Market(
            slug=f"eval-route-market-{index}",
            title=f"Eval route market {index}",
            question="Will the route limit evaluations?",
        )
        for index in range(3)
    ]
    db_session.add_all(markets)
    await db_session.flush()
    for market in markets:
        db_session.add(
            Evaluation(
                market_id=market.id,
                brier_score=Decimal("0.250000"),
                predicted_prob=Decimal("0.5000"),
                actual_outcome=1,
            )
        )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/eval/evaluations", params={"limit": 2})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 2
