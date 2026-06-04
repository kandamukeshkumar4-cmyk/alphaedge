from decimal import Decimal

import pytest

from app.db.models import Evaluation, Market
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
