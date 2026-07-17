from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Account, Pod as PodRow, PodEquitySnapshot, PodTrade
from app.pods.base import Pod, PodDecision, PodMarket, PodScore
from app.pods.registry import PodRegistry


class _FixturePod(Pod):
    key = "fixture"

    def universe(self) -> set[str]:
        return {"Sports"}

    def score_market(self, market: PodMarket) -> PodScore:
        return PodScore(70, {"fixture": 70.0})

    def decide(self, market: PodMarket, score: PodScore) -> PodDecision:
        return PodDecision(action="hold", reason="fixture")


def test_pods_are_disabled_by_default():
    assert Settings(_env_file=None).pods_enabled is False
    assert Settings(_env_file=None).paper_trading_only is True


def test_registry_rejects_duplicate_keys_and_pod_is_pure():
    registry = PodRegistry()
    registry.register(_FixturePod)
    assert registry.keys() == ("fixture",)
    pod = registry.create("fixture", config={"max_bet_fraction": "0.02"})
    assert pod.size(bankroll=Decimal("1000"), price=Decimal("0.50")) == Decimal("40")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_FixturePod)


@pytest.mark.asyncio
async def test_pod_rows_are_isolated_per_dedicated_account(db_session, trader_account):
    second = Account(name="Second pod account", cash_balance=Decimal("1000"))
    db_session.add(second)
    await db_session.flush()
    one = PodRow(key="one", display_name="One", account_id=trader_account.id, config={})
    two = PodRow(key="two", display_name="Two", account_id=second.id, config={})
    db_session.add_all([one, two])
    await db_session.flush()
    db_session.add(PodEquitySnapshot(pod_id=one.id, cash_balance=Decimal("100"), positions_mtm=Decimal("0"), equity=Decimal("100")))
    await db_session.flush()
    rows = (await db_session.execute(select(PodEquitySnapshot).where(PodEquitySnapshot.pod_id == two.id))).scalars().all()
    assert rows == []
    assert (await db_session.execute(select(PodTrade))).scalars().all() == []
