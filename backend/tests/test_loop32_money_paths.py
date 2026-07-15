"""Loop V32 money-path regression tests.

Each case asserts an externally meaningful safety property: rejected orders leave
no persisted trade, NO fills update the correct position and ledger legs, and
risk limits retain their exact boundary semantics.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Account, LedgerEntry, Order, OrderOutcome, OrderSide, OrderType, Position
from app.risk.rules import OrderIntent, RiskService
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService


async def _open_market(db_session, slug: str):
    return await MarketService(db_session).create_market(
        slug=slug,
        title=f"{slug} title",
        question="Will the money-path invariant hold?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("price", "expires_at", "error"),
    [
        (None, None, "Limit orders require price"),
        (Decimal("0.50"), datetime.now(timezone.utc) - timedelta(seconds=1), "expiry"),
    ],
)
async def test_rejected_limit_orders_leave_no_order_or_cash_reservation(
    db_session, price, expires_at, error
):
    market = await _open_market(db_session, f"loop32-rejected-{price is None}")
    account = Account(name="Rejected order account", cash_balance=Decimal("25"))
    db_session.add(account)
    await db_session.flush()

    service = OrderBookService(db_session)
    with pytest.raises(ValueError, match=error):
        await service.submit_order(
            market.id,
            account.id,
            OrderSide.BUY,
            OrderOutcome.YES,
            OrderType.LIMIT,
            Decimal("10"),
            price,
            expires_at=expires_at,
        )

    assert await db_session.scalar(select(Order).where(Order.account_id == account.id)) is None
    assert await service.reserved_cash(account.id) == Decimal("0")
    await db_session.refresh(account)
    assert account.cash_balance == Decimal("25")


@pytest.mark.asyncio
async def test_market_order_without_liquidity_has_no_trade_side_effects(db_session):
    market = await _open_market(db_session, "loop32-empty-market")
    account = Account(name="No liquidity account", cash_balance=Decimal("25"))
    db_session.add(account)
    await db_session.flush()

    with pytest.raises(ValueError, match="No liquidity"):
        await OrderBookService(db_session).submit_order(
            market.id,
            account.id,
            OrderSide.BUY,
            OrderOutcome.YES,
            OrderType.MARKET,
            Decimal("1"),
        )

    assert await db_session.scalar(select(Order).where(Order.account_id == account.id)) is None
    assert (
        await db_session.scalar(select(LedgerEntry).where(LedgerEntry.account_id == account.id))
        is None
    )
    await db_session.refresh(account)
    assert account.cash_balance == Decimal("25")


@pytest.mark.asyncio
async def test_no_fill_updates_no_positions_and_balanced_trade_cash(db_session):
    market = await _open_market(db_session, "loop32-no-fill")
    buyer = Account(name="NO buyer", cash_balance=Decimal("100"))
    seller = Account(name="NO seller", cash_balance=Decimal("100"))
    db_session.add_all([buyer, seller])
    await db_session.flush()

    book = OrderBookService(db_session)
    await book.submit_order(
        market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.NO,
        OrderType.LIMIT,
        Decimal("4"),
        Decimal("0.60"),
    )
    filled = await book.submit_order(
        market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.NO,
        OrderType.LIMIT,
        Decimal("4"),
        Decimal("0.60"),
    )

    assert filled.status.value == "filled"
    assert filled.filled_quantity == Decimal("4")
    positions = (
        await db_session.scalars(
            select(Position).where(Position.market_id == market.id).order_by(Position.account_id)
        )
    ).all()
    no_shares_by_account = {position.account_id: position.no_shares for position in positions}
    assert no_shares_by_account == {buyer.id: Decimal("4"), seller.id: Decimal("-4")}
    await db_session.refresh(buyer)
    await db_session.refresh(seller)
    assert buyer.cash_balance == Decimal("97.6000")
    assert seller.cash_balance == Decimal("102.4000")
    entries = (await db_session.scalars(select(LedgerEntry).where(LedgerEntry.market_id == market.id))).all()
    assert sorted(entry.amount for entry in entries) == [Decimal("-2.4000"), Decimal("2.4000")]


def test_risk_boundary_allows_exact_bet_cap_but_rejects_expired_order():
    common = dict(
        market_slug="nba-2025-01-15-lal-bos",
        side="buy",
        outcome="yes",
        quantity=Decimal("100"),
        price=Decimal("0.50"),
        predicted_prob=0.62,
        confidence=0.70,
        edge=0.05,
        bankroll=Decimal("1000"),
        current_drawdown=0.1499,
        minutes_before_start=5,
    )
    service = RiskService()

    accepted, failures = service.validate(OrderIntent(**common))
    expired, expired_failures = service.validate(
        OrderIntent(**common, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )

    assert accepted is True
    assert failures == []
    assert expired is False
    assert expired_failures == ["order expiry must be in the future"]
