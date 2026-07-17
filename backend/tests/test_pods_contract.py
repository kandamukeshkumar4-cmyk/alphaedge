"""V57 P5 safety contracts for isolated paper strategy pods."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models import Account, Market, OddsSnapshot, Order, Pod as PodRow, PodTrade
from app.pods.base import PricePoint
from app.pods.runner import pod_runner_task
from app.pods.scoring import score_price_history


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


async def _pod_market(db_session, *, now: datetime, lock_at: datetime, max_exposure: str = "0.05"):
    account = Account(name="Contract pod", cash_balance=Decimal("10000"))
    market = Market(
        slug="btc-contract-5m", title="BTC contract", question="BTC?", category="Crypto",
        source="polymarket", lock_at=lock_at,
    )
    db_session.add_all([account, market])
    await db_session.flush()
    pod = PodRow(
        key="crypto_5m_momentum_fade", display_name="Crypto", account_id=account.id,
        config={"entry_threshold": 30, "max_bet_fraction": "0.005", "max_exposure_fraction": max_exposure, "fee_per_contract": "0.002"}, enabled=True,
    )
    db_session.add(pod)
    for offset, price in enumerate(["0.40", "0.44", "0.49", "0.55", "0.61", "0.67"]):
        db_session.add(OddsSnapshot(market_slug=market.slug, implied_yes=Decimal(price), captured_at=now - timedelta(minutes=6 - offset)))
    await db_session.flush()
    return account, market, pod


def test_score_fixture_is_deterministic():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    fixture = tuple(PricePoint(start + timedelta(minutes=i), Decimal(value)) for i, value in enumerate(["0.41", "0.44", "0.48", "0.53", "0.58"]))
    assert score_price_history(fixture) == score_price_history(fixture)


@pytest.mark.asyncio
async def test_runner_enforces_pod_exposure_cap_before_order_submission(db_session):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    account, _market, _pod = await _pod_market(db_session, now=now, lock_at=now + timedelta(minutes=10), max_exposure="0.001")
    summary = await pod_runner_task({"settings": SimpleNamespace(pods_enabled=True), "session_factory": _SessionFactory(db_session), "now": now})
    assert summary["entered"] == 0
    assert (await db_session.execute(select(Order).where(Order.account_id == account.id))).scalars().all() == []
    trade = (await db_session.execute(select(PodTrade).where(PodTrade.pod_id == _pod.id))).scalar_one()
    assert trade.decision["rejected"] == "pod max exposure cap"


@pytest.mark.asyncio
async def test_runner_excludes_post_close_market_and_never_records_a_trade(db_session):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    account, _market, pod = await _pod_market(db_session, now=now, lock_at=now - timedelta(seconds=1))
    summary = await pod_runner_task({"settings": SimpleNamespace(pods_enabled=True), "session_factory": _SessionFactory(db_session), "now": now})
    assert summary["entered"] == 0
    assert summary["scored"] == 0
    assert (await db_session.execute(select(Order).where(Order.account_id == account.id))).scalars().all() == []
    assert (await db_session.execute(select(PodTrade).where(PodTrade.pod_id == pod.id))).scalars().all() == []


def test_runner_uses_the_required_validated_order_path_only():
    source = Path("app/pods/runner.py").read_text(encoding="utf-8")
    assert "RiskService().validate(intent)" in source
    assert "OrderBookService(session" in source
    assert ".submit_order(" in source
    assert "PAPER_TRADING_ONLY" not in source  # settings/risk owns the invariant; no bypass switch
