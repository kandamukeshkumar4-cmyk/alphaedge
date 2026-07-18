"""Loop V69 — confirmed pod review finding fixes."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

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


# --- (4) pod equity snapshots -------------------------------------------------


@pytest.mark.asyncio
async def test_runner_writes_equity_snapshot_per_pod_pass(db_session):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    account = Account(name="Equity pod", cash_balance=Decimal("10000"))
    market = Market(
        slug="btc-eq-5m",
        title="BTC eq",
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
            "entry_threshold": 101,
            "max_bet_fraction": "0.005",
            "max_exposure_fraction": "0.05",
            "fee_per_contract": "0.002",
        },
        enabled=True,
    )
    db_session.add(pod)
    for offset, price in enumerate(["0.40", "0.44", "0.49"]):
        db_session.add(
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal(price),
                captured_at=now - timedelta(minutes=3 - offset),
            )
        )
    await db_session.flush()

    before = (
        await db_session.execute(
            select(PodEquitySnapshot).where(PodEquitySnapshot.pod_id == pod.id)
        )
    ).scalars().all()
    assert before == []

    summary = await pod_runner_task(
        {
            "settings": SimpleNamespace(pods_enabled=True),
            "session_factory": _SessionFactory(db_session),
            "now": now,
        }
    )
    assert summary.get("skipped") is not True
    snaps = (
        await db_session.execute(
            select(PodEquitySnapshot).where(PodEquitySnapshot.pod_id == pod.id)
        )
    ).scalars().all()
    assert len(snaps) == 1
    assert snaps[0].cash_balance == Decimal("10000")
    assert snaps[0].positions_mtm == Decimal("0")
    assert snaps[0].equity == Decimal("10000")
    captured = snaps[0].captured_at
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    assert captured == now


# --- (5) leakage: as_of, model filter, news fetched_at ------------------------


@pytest.mark.asyncio
async def test_latest_model_probability_filters_predicted_at_as_of(db_session):
    from app.pods.runner import _latest_model_probability

    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    db_session.add(
        PredictionLog(
            market_slug="leak-mkt",
            predicted_prob=Decimal("0.40"),
            confidence=Decimal("0.5"),
            predicted_at=now - timedelta(hours=1),
        )
    )
    db_session.add(
        PredictionLog(
            market_slug="leak-mkt",
            predicted_prob=Decimal("0.90"),
            confidence=Decimal("0.5"),
            predicted_at=now + timedelta(hours=1),
        )
    )
    await db_session.flush()

    prob = await _latest_model_probability(db_session, "leak-mkt", as_of=now)
    assert prob == pytest.approx(0.40)


@pytest.mark.asyncio
async def test_build_market_context_accepts_as_of_and_honest_news_timestamps(
    db_session,
):
    from app.services.master_context import build_market_context
    from app.signals import news_signal as news_mod
    from app.signals.news_signal import NewsSignal, cache_signal

    now = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)
    fetched = datetime(2026, 6, 1, 14, 0, tzinfo=UTC)
    news_mod._CACHE.clear()
    cache_signal(
        NewsSignal(
            topic="ctx-slug",
            sentiment_score=0.1,
            volume_score=0.2,
            polymarket_consensus=None,
            headline="h",
            sources_count=1,
        ),
        fetched_at=fetched,
    )
    ctx = await build_market_context(db_session, "ctx-slug", as_of=now)
    assert ctx["as_of"] == now.isoformat()
    assert ctx["generated_at"] == now.isoformat()
    assert ctx["news"]["available"] is True
    assert ctx["news"]["fetched_at"] == fetched.isoformat()
    assert ctx["news"]["captured_at"] == fetched.isoformat()
    # Must not stamp read/generation time as capture.
    assert ctx["news"]["captured_at"] != now.isoformat()


@pytest.mark.asyncio
async def test_news_block_null_when_cache_empty(db_session):
    from app.services.master_context import _news_block
    from app.signals import news_signal as news_mod

    news_mod._CACHE.clear()
    block = await _news_block("no-cache-slug")
    assert block["available"] is False
    assert block["captured_at"] is None
    assert block["fetched_at"] is None


# --- (6) price_delta_1h latest-minus-oldest -----------------------------------


@pytest.mark.asyncio
async def test_price_delta_1h_is_latest_minus_oldest_not_two_oldest(db_session, monkeypatch):
    """Three snapshots in window: delta must be newest - oldest, not row1-row0 only."""
    from app.db.models import MarketStatus
    from app.workers import tasks as worker_tasks

    now = datetime(2026, 3, 1, 12, tzinfo=UTC)
    market = Market(
        slug="delta-1h-mkt",
        title="Delta",
        question="?",
        category="Politics",
        source="polymarket",
        status=MarketStatus.OPEN,
        volume=1_000_000,
        lock_at=now + timedelta(hours=2),
    )
    db_session.add(market)
    # oldest 0.20, middle 0.50, newest 0.80 → correct delta = +0.60
    # Bug of "two oldest" would yield 0.50 - 0.20 = +0.30
    for minutes, price in ((50, "0.20"), (30, "0.50"), (5, "0.80")):
        db_session.add(
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=Decimal(price),
                captured_at=now - timedelta(minutes=minutes),
            )
        )
    await db_session.flush()

    captured: dict[str, float | None] = {}

    async def fake_fetch(topic, **kw):
        return None

    from app.signals.news_cadence import eligible_candidates

    real_eligible = eligible_candidates

    def capture_eligible(candidates, **kwargs):
        for c in candidates:
            if c.slug == market.slug:
                captured["delta"] = c.price_delta_1h
        return real_eligible(candidates, **kwargs)

    monkeypatch.setattr("app.signals.news_signal.fetch_news_signal", fake_fetch)
    monkeypatch.setattr(
        "app.signals.news_cadence.eligible_candidates", capture_eligible
    )
    settings = SimpleNamespace(
        news_cadence_enabled=True,
        news_cadence_budget=10,
        news_cadence_price_jump=0.01,
        news_cadence_whale_spike=0.01,
    )
    await worker_tasks.run_news_scan(db_session, settings=settings, now=now)
    assert "delta" in captured
    assert captured["delta"] == pytest.approx(0.60)
