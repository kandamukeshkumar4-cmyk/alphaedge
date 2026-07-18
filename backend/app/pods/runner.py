"""Flag-gated in-process execution for isolated paper strategy pods."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.fill_model import compute_fill
from app.core.config import get_settings
from app.db.models import (
    Account,
    Market,
    MarketStatus,
    Order,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
    Pod as PodRow,
    PodTrade,
    Position,
    PredictionLog,
)
from app.db.session import AsyncSessionLocal
from app.pods.base import PodDecision, PodMarket
from app.pods.costs import estimate_entry_fee
from app.pods.registry import registry
from app.pods.scoring import load_preclose_history, record_score
from app.risk.rules import OrderIntent, RiskService
from app.services.order_book_service import OrderBookService

# Importing the module registers the three explicitly declared pod types.
from app.pods import strategies as _strategies  # noqa: F401

logger = logging.getLogger(__name__)

POD_RUNNER_INTERVAL_SEC = 60
DEFAULT_POD_BANKROLL = Decimal("10000")
DEFAULT_POD_CONFIGS: dict[str, dict[str, Any]] = {
    "crypto_5m_momentum_fade": {"max_bet_fraction": "0.02", "max_exposure_fraction": "0.10", "fee_per_contract": "0.002"},
    "longshot_fade": {"max_bet_fraction": "0.02", "max_exposure_fraction": "0.08", "fee_per_contract": "0.002"},
    "sports_value": {"max_bet_fraction": "0.03", "max_exposure_fraction": "0.10", "fee_per_contract": "0.002"},
}


def pod_detail(summary: dict[str, Any] | None) -> str | None:
    if not summary:
        return None
    if summary.get("skipped"):
        return f"disabled: {summary.get('reason', 'unknown')}"
    return " ".join(f"{key}={int(summary.get(key, 0))}" for key in ("scanned", "scored", "entered", "exited"))


async def ensure_default_pods(session: AsyncSession) -> list[PodRow]:
    """Provision one account-backed row per registered strategy, idempotently.

    New pods default to enabled=False (per-pod opt-in). Registry keys missing
    from DEFAULT_POD_CONFIGS are skipped with a warning — never KeyError.
    """
    existing = {
        pod.key: pod
        for pod in (await session.execute(select(PodRow))).scalars().all()
    }
    for key in registry.keys():
        if key in existing:
            continue
        config = DEFAULT_POD_CONFIGS.get(key)
        if config is None:
            logger.warning(
                "skipping registered pod %s: missing DEFAULT_POD_CONFIGS entry",
                key,
            )
            continue
        account = Account(name=f"Pod: {key}", cash_balance=DEFAULT_POD_BANKROLL)
        session.add(account)
        await session.flush()
        pod = PodRow(
            key=key,
            display_name=key.replace("_", " ").title(),
            account_id=account.id,
            config=dict(config),
            enabled=False,
        )
        session.add(pod)
        await session.flush()
        existing[key] = pod
    return [existing[key] for key in sorted(existing)]


async def _latest_model_probability(
    session: AsyncSession, market_slug: str
) -> float | None:
    probability = await session.scalar(
        select(PredictionLog.predicted_prob)
        .where(PredictionLog.market_slug == market_slug)
        .order_by(PredictionLog.predicted_at.desc())
        .limit(1)
    )
    return float(probability) if probability is not None else None


async def _position_value(session: AsyncSession, account_id) -> Decimal:
    """Filled position capital at cost for the pod account (positions table)."""
    rows = (
        await session.execute(
            select(
                Position.yes_shares,
                Position.avg_yes_cost,
                Position.no_shares,
                Position.avg_no_cost,
            ).where(
                Position.account_id == account_id,
                Position.settled.is_(False),
            )
        )
    ).all()
    total = Decimal("0")
    for yes_shares, avg_yes, no_shares, avg_no in rows:
        yes = Decimal(yes_shares or 0)
        no = Decimal(no_shares or 0)
        if yes > 0:
            total += yes * Decimal(avg_yes or 0)
        if no > 0:
            total += no * Decimal(avg_no or 0)
    return total


async def _open_exposure(session: AsyncSession, account_id) -> Decimal:
    """Resting order residual + filled position value (cannot ignore fills)."""
    resting = await session.scalar(
        select(
            func.coalesce(
                func.sum(Order.price * (Order.quantity - Order.filled_quantity)),
                Decimal("0"),
            )
        ).where(
            Order.account_id == account_id,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
        )
    )
    filled = await _position_value(session, account_id)
    return Decimal(resting or 0) + filled


async def _entry_count(session: AsyncSession, *, pod_id, market_id) -> int:
    """Successful enter trades for pod+market (idempotency sequence)."""
    count = await session.scalar(
        select(func.count())
        .select_from(PodTrade)
        .where(
            PodTrade.pod_id == pod_id,
            PodTrade.market_id == market_id,
            PodTrade.action == "enter",
        )
    )
    return int(count or 0)


def _minutes_until_close(market: Market, now: datetime) -> int:
    if market.lock_at is None:
        return 60
    close_at = market.lock_at.replace(tzinfo=UTC) if market.lock_at.tzinfo is None else market.lock_at
    return max(0, int((close_at - now).total_seconds() // 60))


async def _process_market(
    session: AsyncSession,
    *,
    pod_row: PodRow,
    account: Account,
    market: Market,
    now: datetime,
) -> tuple[bool, bool]:
    """Score one safe pre-close market and submit only a validated CLOB order."""
    if market.lock_at is not None and _minutes_until_close(market, now) <= 0:
        return False, False
    history = await load_preclose_history(session, market_slug=market.slug, as_of=now)
    if not history:
        return False, False
    # Defensive invariant: the query already applies this filter. Keep the
    # explicit check close to execution so post-close data can never leak.
    if any(point.captured_at > now for point in history):
        raise ValueError("post-decision snapshot rejected")
    price = history[-1].implied_yes
    pod = registry.create(pod_row.key, config=pod_row.config)
    # V61 S4: a read-only context snapshot enriches pod inputs. Strategy code
    # remains pure and the existing RiskService -> OrderIntent -> order-book path
    # remains the only possible execution path below.
    from app.services.master_context import build_market_context

    context = await build_market_context(session, market.slug)
    market_view = PodMarket(
        market_id=str(market.id),
        slug=market.slug,
        category=market.category,
        price=price,
        close_at=market.lock_at,
        as_of=now,
        price_history=history,
        metadata={
            "source": market.source,
            "title": market.title,
            "model_probability": await _latest_model_probability(session, market.slug),
            "sentiment_trend": context["sentiment_trend"],
            "sentiment_debate": context["sentiment_debate"],
        },
    )
    score = pod.score_market(market_view)
    decision = pod.decide(market_view, score)
    trade = await record_score(
        session,
        pod_id=pod_row.id,
        market_id=market.id,
        score=score,
        decision={"reason": decision.reason, "action": decision.action},
    )
    if not decision.is_entry:
        return True, False
    return True, await _submit_decision(
        session,
        pod_row=pod_row,
        account=account,
        market=market,
        decision=decision,
        trade=trade,
        now=now,
    )


async def _submit_decision(
    session: AsyncSession,
    *,
    pod_row: PodRow,
    account: Account,
    market: Market,
    decision: PodDecision,
    trade: PodTrade,
    now: datetime,
) -> bool:
    if not all((decision.outcome, decision.price, decision.predicted_prob is not None, decision.confidence is not None, decision.edge is not None)):
        trade.decision = {**trade.decision, "rejected": "incomplete entry decision"}
        return False
    assert decision.price is not None
    quantity = pod_quantity = registry.create(pod_row.key, config=pod_row.config).size(
        bankroll=account.cash_balance, price=decision.price
    )
    if pod_quantity <= 0:
        trade.decision = {**trade.decision, "rejected": "zero quantity"}
        return False
    fill = compute_fill(
        "yes_buy" if decision.outcome == "yes" else "no_buy",
        float(decision.price if decision.outcome == "yes" else Decimal("1") - decision.price),
        size=float(quantity),
    )
    limit_price = Decimal(str(fill.fill_price)).quantize(Decimal("0.0001"))
    try:
        fee = estimate_entry_fee(source=market.source, price=limit_price, quantity=quantity, config=pod_row.config)
    except ValueError as exc:
        trade.decision = {**trade.decision, "rejected": str(exc)}
        return False
    cap_fraction = Decimal(str(pod_row.config.get("max_exposure_fraction", "0.05")))
    max_exposure = account.cash_balance * min(cap_fraction, Decimal("0.05"))
    proposed = limit_price * quantity + fee
    if await _open_exposure(session, account.id) + proposed > max_exposure:
        trade.decision = {**trade.decision, "rejected": "pod max exposure cap"}
        return False
    intent = OrderIntent(
        market_slug=market.slug,
        side="buy",
        outcome=decision.outcome,
        quantity=quantity,
        price=limit_price,
        predicted_prob=float(decision.predicted_prob),
        confidence=float(decision.confidence),
        edge=float(decision.edge),
        bankroll=account.cash_balance,
        current_drawdown=0.0,
        minutes_before_start=_minutes_until_close(market, now),
        agent_enabled=True,
    )
    accepted, failures = RiskService().validate(intent)
    if not accepted:
        trade.decision = {**trade.decision, "rejected": "; ".join(failures)}
        return False
    # Key on pod+market+entry-count (not wall-clock minute) so same-minute
    # refills cannot mint a new order after a fill while the cap is still hit.
    entries = await _entry_count(session, pod_id=pod_row.id, market_id=market.id)
    order = await OrderBookService(session, correlation_id=f"pod:{pod_row.key}").submit_order(
        market_id=market.id,
        account_id=account.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome(decision.outcome),
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=limit_price,
        idempotency_key=f"pod:{pod_row.id}:{market.id}:{entries}",
    )
    trade.action = "enter"
    trade.outcome = decision.outcome
    trade.price = limit_price
    trade.quantity = quantity
    trade.fee = fee
    trade.slippage = Decimal(str(fill.slippage_abs)).quantize(Decimal("0.0001"))
    trade.order_id = order.id
    trade.decision = {**trade.decision, "status": "submitted", "order_id": str(order.id)}
    return True


async def pod_runner_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """Run one bounded pod pass; global flag default is safely disabled."""
    settings = ctx.get("settings") or get_settings()
    if not settings.pods_enabled:
        return {"skipped": True, "reason": "PODS_ENABLED=false", "scanned": 0, "scored": 0, "entered": 0, "exited": 0}
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    now = ctx.get("now") or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    summary = {"scanned": 0, "scored": 0, "entered": 0, "exited": 0}
    async with session_factory() as session:
        pods = [pod for pod in await ensure_default_pods(session) if pod.enabled]
        markets = (
            await session.execute(
                select(Market)
                .where(Market.status == MarketStatus.OPEN)
                .order_by(Market.lock_at.asc().nullslast(), Market.id.asc())
                .limit(100)
            )
        ).scalars().all()
        accounts = {account.id: account for account in (await session.execute(select(Account).where(Account.id.in_([pod.account_id for pod in pods])))).scalars().all()}
        for pod in pods:
            account = accounts[pod.account_id]
            for market in markets:
                summary["scanned"] += 1
                try:
                    scored, entered = await _process_market(session, pod_row=pod, account=account, market=market, now=now)
                except Exception:  # noqa: BLE001 - one pod/market must not stop the loop
                    summary.setdefault("errors", 0)
                    summary["errors"] += 1
                    continue
                summary["scored"] += int(scored)
                summary["entered"] += int(entered)
        await session.commit()
    return summary
