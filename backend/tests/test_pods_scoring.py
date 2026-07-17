from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Account, Market, OddsSnapshot, Pod as PodRow, PodTrade
from app.pods.base import PricePoint
from app.pods.scoring import load_preclose_history, record_score, score_price_history


def _history(values: list[str]) -> tuple[PricePoint, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        PricePoint(captured_at=start + timedelta(minutes=index), implied_yes=Decimal(value))
        for index, value in enumerate(values)
    )


def test_score_is_deterministic_and_has_all_factors():
    history = _history(["0.40", "0.43", "0.47", "0.52", "0.57", "0.61"])
    first = score_price_history(history)
    assert first == score_price_history(history)
    assert set(first.components) == {
        "liquidity", "trend_strength", "rsi_pressure", "move_persistence", "bounce_quality"
    }
    assert 0 <= first.value <= 100
    assert score_price_history(_history(["0.5", "0.5"])).value == 0


@pytest.mark.asyncio
async def test_history_excludes_snapshots_after_decision_time(db_session):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    db_session.add_all(
        [
            OddsSnapshot(market_slug="pod-history", implied_yes=Decimal("0.45"), captured_at=now - timedelta(minutes=1)),
            OddsSnapshot(market_slug="pod-history", implied_yes=Decimal("0.55"), captured_at=now + timedelta(minutes=1)),
        ]
    )
    await db_session.flush()
    history = await load_preclose_history(db_session, market_slug="pod-history", as_of=now)
    assert [point.implied_yes for point in history] == [Decimal("0.45")]


@pytest.mark.asyncio
async def test_record_score_persists_components_for_below_threshold_hold(db_session):
    account = Account(name="score pod", cash_balance=Decimal("1000"))
    market = Market(slug="score-market", title="Score", question="Score?")
    db_session.add_all([account, market])
    await db_session.flush()
    pod = PodRow(key="score", display_name="Score", account_id=account.id, config={})
    db_session.add(pod)
    await db_session.flush()
    score = score_price_history(_history(["0.40", "0.42", "0.45", "0.47"]))
    await record_score(db_session, pod_id=pod.id, market_id=market.id, score=score, decision={"threshold": 70})
    row = (await db_session.execute(select(PodTrade))).scalar_one()
    assert row.action == "hold"
    assert row.score == score.value
    assert row.score_components == dict(score.components)
