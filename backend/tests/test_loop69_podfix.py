"""Loop V69 — confirmed pod review finding fixes."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import (
    Account,
    Market,
    OddsSnapshot,
    Order,
    Pod as PodRow,
    PodEquitySnapshot,
    PodTrade,
    Position,
    PredictionLog,
)
from app.pods.runner import (
    _entry_count,
    _open_exposure,
    _position_value,
    ensure_default_pods,
    pod_runner_task,
)
from app.pods.strategies import LongshotFadePod
from app.pods.base import PodMarket, PricePoint


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


# --- (1) CRITICAL exposure + entry idempotency --------------------------------


@pytest.mark.asyncio
async def test_open_exposure_includes_filled_position_value(db_session):
    account = Account(name="Exposure pod", cash_balance=Decimal("10000"))
    market = Market(
        slug="exp-mkt",
        title="Exp",
        question="?",
        category="Crypto",
        source="polymarket",
    )
    db_session.add_all([account, market])
    await db_session.flush()
    db_session.add(
        Position(
            account_id=account.id,
            market_id=market.id,
            yes_shares=Decimal("0"),
            no_shares=Decimal("100"),
            avg_yes_cost=Decimal("0"),
            avg_no_cost=Decimal("0.40"),
            settled=False,
        )
    )
    await db_session.flush()

    assert await _position_value(db_session, account.id) == Decimal("40.0000")
    # No resting orders — filled position capital must still count.
    assert await _open_exposure(db_session, account.id) == Decimal("40.0000")


@pytest.mark.asyncio
async def test_entry_idempotency_key_uses_entry_count_not_minute(db_session):
    now = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    account = Account(name="Idem pod", cash_balance=Decimal("10000"))
    market = Market(
        slug="btc-idem-5m",
        title="BTC",
        question="?",
        category="Crypto",
        source="polymarket",
        lock_at=now + timedelta(minutes=10),
    )
    db_session.add_all([account, market])
    await db_session.flush()
    pod = PodRow(
        key="crypto_5m_momentum_fade",
        display_name="Crypto",
        account_id=account.id,
        config={
            "entry_threshold": 30,
            "max_bet_fraction": "0.005",
            "max_exposure_fraction": "0.05",
            "fee_per_contract": "0.002",
        },
        enabled=True,
    )
    db_session.add(pod)
    for offset, price in enumerate(["0.40", "0.44", "0.49", "0.55", "0.61", "0.67"]):
        db_session.add(
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal(price),
                captured_at=now - timedelta(minutes=6 - offset),
            )
        )
    await db_session.flush()

    assert await _entry_count(db_session, pod_id=pod.id, market_id=market.id) == 0
    summary = await pod_runner_task(
        {
            "settings": SimpleNamespace(pods_enabled=True),
            "session_factory": _SessionFactory(db_session),
            "now": now,
        }
    )
    assert summary["entered"] == 1, summary
    order = (
        await db_session.execute(select(Order).where(Order.account_id == account.id))
    ).scalar_one()
    assert order.idempotency_key == f"pod:{pod.id}:{market.id}:0"
    assert now.strftime("%Y%m%d%H%M") not in (order.idempotency_key or "")
    assert await _entry_count(db_session, pod_id=pod.id, market_id=market.id) == 1


@pytest.mark.asyncio
async def test_filled_position_blocks_refill_against_exposure_cap(db_session):
    """After a fill, position value counts toward cap — minute re-entry blocked."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    account = Account(name="Cap pod", cash_balance=Decimal("1000"))
    market = Market(
        slug="btc-cap-5m",
        title="BTC cap",
        question="?",
        category="Crypto",
        source="polymarket",
        lock_at=now + timedelta(minutes=10),
    )
    db_session.add_all([account, market])
    await db_session.flush()
    # Position already consumes the entire 5% cap (1000 * 0.05 = 50).
    db_session.add(
        Position(
            account_id=account.id,
            market_id=market.id,
            yes_shares=Decimal("0"),
            no_shares=Decimal("125"),
            avg_yes_cost=Decimal("0"),
            avg_no_cost=Decimal("0.40"),
            settled=False,
        )
    )
    pod = PodRow(
        key="crypto_5m_momentum_fade",
        display_name="Crypto",
        account_id=account.id,
        config={
            "entry_threshold": 30,
            "max_bet_fraction": "0.005",
            "max_exposure_fraction": "0.05",
            "fee_per_contract": "0.002",
        },
        enabled=True,
    )
    db_session.add(pod)
    for offset, price in enumerate(["0.40", "0.44", "0.49", "0.55", "0.61", "0.67"]):
        db_session.add(
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal(price),
                captured_at=now - timedelta(minutes=6 - offset),
            )
        )
    await db_session.flush()

    summary = await pod_runner_task(
        {
            "settings": SimpleNamespace(pods_enabled=True),
            "session_factory": _SessionFactory(db_session),
            "now": now,
        }
    )
    assert summary["entered"] == 0
    orders = (
        await db_session.execute(select(Order).where(Order.account_id == account.id))
    ).scalars().all()
    assert orders == []
    trade = (
        await db_session.execute(select(PodTrade).where(PodTrade.pod_id == pod.id))
    ).scalar_one()
    assert trade.decision.get("rejected") == "pod max exposure cap"


# --- (2) pods seeding ---------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_default_pods_seeds_disabled_opt_in(db_session):
    pods = await ensure_default_pods(db_session)
    keys = {pod.key for pod in pods}
    assert {"crypto_5m_momentum_fade", "longshot_fade", "sports_value"}.issubset(keys)
    for pod in pods:
        if pod.key in {
            "crypto_5m_momentum_fade",
            "longshot_fade",
            "sports_value",
        }:
            assert pod.enabled is False


@pytest.mark.asyncio
async def test_ensure_default_pods_skips_registry_keys_missing_config(
    db_session, monkeypatch, caplog
):
    import logging

    from app.pods import runner as runner_mod
    from app.pods.base import Pod, PodDecision, PodScore
    from app.pods.registry import PodRegistry

    class GhostPod(Pod):
        key = "ghost_unconfigured"

        def universe(self):
            return {"Sports"}

        def score_market(self, market):
            return PodScore(0, {})

        def decide(self, market, score):
            return PodDecision(action="hold", reason="ghost")

    reg = PodRegistry()
    reg.register(GhostPod)
    # Keep the real three so DEFAULT_POD_CONFIGS path still works.
    from app.pods.strategies import (
        CryptoMomentumFadePod,
        LongshotFadePod,
        SportsValuePod,
    )

    reg.register(CryptoMomentumFadePod)
    reg.register(LongshotFadePod)
    reg.register(SportsValuePod)
    monkeypatch.setattr(runner_mod, "registry", reg)

    with caplog.at_level(logging.WARNING, logger="app.pods.runner"):
        pods = await ensure_default_pods(db_session)

    assert "ghost_unconfigured" not in {p.key for p in pods}
    assert any("ghost_unconfigured" in r.message for r in caplog.records)


# --- (3) LongshotFadePod universe enforcement ---------------------------------


def _price_history() -> tuple[PricePoint, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        PricePoint(start + timedelta(minutes=i), Decimal(v))
        for i, v in enumerate(["0.80", "0.82", "0.84", "0.86", "0.88", "0.90"])
    )


def test_longshot_decide_rejects_category_outside_universe():
    pod = LongshotFadePod(config={"entry_threshold": 30, "fee_per_contract": "0.002"})
    market = PodMarket(
        market_id="m",
        slug="other-cat",
        category="Entertainment",
        price=Decimal("0.90"),
        as_of=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=6),
        price_history=_price_history(),
        metadata={"source": "polymarket"},
    )
    decision = pod.decide(market, pod.score_market(market))
    assert decision.action == "hold"
    assert "outside longshot universe" in decision.reason


def test_longshot_decide_allows_declared_universe_category():
    pod = LongshotFadePod(config={"entry_threshold": 30, "fee_per_contract": "0.002"})
    market = PodMarket(
        market_id="m",
        slug="politics-fav",
        category="Politics",
        price=Decimal("0.90"),
        as_of=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=6),
        price_history=_price_history(),
        metadata={"source": "polymarket"},
    )
    decision = pod.decide(market, pod.score_market(market))
    assert decision.action == "enter"
    assert decision.outcome == "no"
