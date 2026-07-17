from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.system import _ALL_LOOPS
from app.db.models import Account, Market, OddsSnapshot, Order, Pod as PodRow, PodEquitySnapshot, PodTrade
from app.db.session import get_db
from app.main import app
from app.observability import loop_state
from app.observability.loop_state import LOOP_INTERVALS
from app.pods.runner import pod_detail, pod_runner_task


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_runner_is_flag_gated(db_session):
    summary = await pod_runner_task({"settings": SimpleNamespace(pods_enabled=False)})
    assert summary["skipped"] is True
    assert pod_detail(summary) == "disabled: PODS_ENABLED=false"


@pytest.mark.asyncio
async def test_runner_submits_only_through_risk_gated_clob_path(db_session):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    account = Account(name="Crypto pod", cash_balance=Decimal("10000"))
    market = Market(
        slug="btc-up-5m", title="BTC 5m", question="BTC up?", category="Crypto",
        source="polymarket", lock_at=now + timedelta(minutes=10),
    )
    db_session.add_all([account, market])
    await db_session.flush()
    db_session.add(PodRow(
        key="crypto_5m_momentum_fade", display_name="Crypto", account_id=account.id,
        config={"entry_threshold": 30, "max_bet_fraction": "0.005", "max_exposure_fraction": "0.05", "fee_per_contract": "0.002"}, enabled=True,
    ))
    for offset, price in enumerate(["0.40", "0.44", "0.49", "0.55", "0.61", "0.67"]):
        db_session.add(OddsSnapshot(market_slug=market.slug, implied_yes=Decimal(price), captured_at=now - timedelta(minutes=6 - offset)))
    await db_session.flush()
    summary = await pod_runner_task({"settings": SimpleNamespace(pods_enabled=True), "session_factory": _SessionFactory(db_session), "now": now})
    assert summary["entered"] == 1, summary
    order = (await db_session.execute(select(Order).where(Order.account_id == account.id))).scalar_one()
    assert order.market_id == market.id
    trade = (await db_session.execute(select(PodTrade).where(PodTrade.order_id == order.id))).scalar_one()
    assert trade.action == "enter"
    assert trade.fee > 0
    assert trade.slippage > 0
    assert "submitted" == trade.decision["status"]


@pytest.mark.asyncio
async def test_runner_passes_read_only_sentiment_context_to_pod(db_session, monkeypatch):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    account = Account(name="Sentiment pod", cash_balance=Decimal("10000"))
    market = Market(slug="sentiment-pod", title="Sentiment", question="?", category="Crypto", source="polymarket", lock_at=now + timedelta(minutes=10))
    db_session.add_all([account, market])
    await db_session.flush()
    db_session.add(PodRow(key="crypto_5m_momentum_fade", display_name="Crypto", account_id=account.id, config={"entry_threshold": 101}, enabled=True))
    for offset, price in enumerate(["0.40", "0.44", "0.49"]):
        db_session.add(OddsSnapshot(market_slug=market.slug, implied_yes=Decimal(price), captured_at=now - timedelta(minutes=3 - offset)))
    await db_session.flush()

    async def fake_context(*_args, **_kwargs):
        return {"sentiment_trend": {"available": True, "direction": 0.2}, "sentiment_debate": {"available": False, "reason": "disabled"}}

    from app.pods.base import PodDecision, PodScore

    captured = {}

    class FakePod:
        def score_market(self, market_view):
            captured.update(market_view.metadata)
            return PodScore(0, {})

        def decide(self, _market_view, _score):
            return PodDecision(action="hold", reason="test")

    monkeypatch.setattr("app.services.master_context.build_market_context", fake_context)
    monkeypatch.setattr("app.pods.runner.registry.create", lambda *_args, **_kwargs: FakePod())
    summary = await pod_runner_task({"settings": SimpleNamespace(pods_enabled=True), "session_factory": _SessionFactory(db_session), "now": now})
    assert summary["scored"] >= 1
    assert captured["sentiment_trend"]["direction"] == 0.2
    assert captured["sentiment_debate"]["available"] is False


@pytest.mark.asyncio
async def test_status_endpoint_is_public_and_surfaces_persisted_curve_and_decisions(db_session):
    account = Account(name="Status pod", cash_balance=Decimal("100"))
    db_session.add(account)
    await db_session.flush()
    pod = PodRow(key="status", display_name="Status", account_id=account.id, config={}, enabled=False)
    db_session.add(pod)
    await db_session.flush()
    db_session.add(PodEquitySnapshot(pod_id=pod.id, cash_balance=Decimal("100"), positions_mtm=Decimal("0"), equity=Decimal("100")))
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/pods")
        assert response.status_code == 200
        body = response.json()
        assert body["paper_trading_only"] is True
        assert body["pods"][0]["equity_curve"][0]["equity"] == "100.0000"
    finally:
        app.dependency_overrides.clear()


def test_pod_runner_is_wired_to_public_heartbeat_contract():
    assert "pod_runner" in _ALL_LOOPS
    assert LOOP_INTERVALS["pod_runner"] == 60
    loop_state.reset()
    loop_state.record_heartbeat("pod_runner", detail=pod_detail({"scanned": 3, "scored": 2, "entered": 1, "exited": 0}))
    assert loop_state.snapshot()["pod_runner"]["detail"] == "scanned=3 scored=2 entered=1 exited=0"
