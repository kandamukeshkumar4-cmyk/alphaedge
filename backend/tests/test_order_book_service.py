from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import (
    Account,
    Fill,
    LedgerEntry,
    LedgerEntryType,
    Order,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)
from app.services.ledger_service import LedgerService
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService
from app.market.order_book import MatchResult, Outcome


@pytest.mark.asyncio
async def test_ledger_credit_and_debit_write_balanced_entries(db_session):
    account = Account(name="Ledger Unit Account", cash_balance=Decimal("0"))
    db_session.add(account)
    await db_session.flush()

    ledger = LedgerService(db_session)
    await ledger.credit(account.id, Decimal("100"), LedgerEntryType.DEPOSIT, "seed")
    await ledger.debit(account.id, Decimal("25"), LedgerEntryType.TRADE, "trade")

    await db_session.refresh(account)
    entries = (
        await db_session.scalars(
            select(LedgerEntry).where(LedgerEntry.account_id == account.id)
        )
    ).all()

    assert account.cash_balance == Decimal("75.0000")
    assert [entry.amount for entry in entries] == [Decimal("100.0000"), Decimal("-25.0000")]
    assert [entry.balance_after for entry in entries] == [
        Decimal("100.0000"),
        Decimal("75.0000"),
    ]


@pytest.mark.asyncio
async def test_order_book_service_rehydrates_open_orders_across_instances(db_session):
    market = await MarketService(db_session).create_market(
        slug="service-rehydrate-market",
        title="Service rehydrate market",
        question="Will another service instance see resting liquidity?",
    )
    buyer = Account(name="Resting Buyer", cash_balance=Decimal("100"))
    seller = Account(name="Crossing Seller", cash_balance=Decimal("100"))
    db_session.add_all([buyer, seller])
    await db_session.flush()

    first_service = OrderBookService(db_session)
    await first_service.submit_order(
        market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.60"),
    )

    second_service = OrderBookService(db_session)
    snapshot = await second_service.get_l2(market.id)
    assert snapshot["yes"]["bids"] == [{"price": 0.6, "size": 10.0}]

    crossing = await second_service.submit_order(
        market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.55"),
    )

    assert crossing.filled_quantity == Decimal("10.0000")
    assert crossing.status.value == "filled"


@pytest.mark.asyncio
async def test_ledger_debit_cannot_overdraw(db_session):
    """Audit H-REL-01: a debit that would drive cash_balance negative must
    raise under the account lock, not persist a negative balance."""
    account = Account(name="Overdraw Guard Account", cash_balance=Decimal("10"))
    db_session.add(account)
    await db_session.flush()

    ledger = LedgerService(db_session)
    with pytest.raises(ValueError, match="overdraw"):
        await ledger.debit(account.id, Decimal("25"), LedgerEntryType.TRADE, "too big")

    await db_session.refresh(account)
    assert account.cash_balance == Decimal("10.0000")  # unchanged


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "shares_attr", "cost_attr"),
    [
        (OrderOutcome.YES, "yes_shares", "avg_yes_cost"),
        (OrderOutcome.NO, "no_shares", "avg_no_cost"),
    ],
)
async def test_scaled_long_uses_weighted_average_and_sets_new_short_basis_after_crossing_zero(
    db_session, outcome, shares_attr, cost_attr
):
    market = await MarketService(db_session).create_market(
        slug=f"weighted-average-{outcome.value}",
        title="Weighted-average position test",
        question="Does a scaled position retain its true entry basis?",
    )
    buyer = Account(name=f"{outcome.value} buyer", cash_balance=Decimal("100"))
    seller = Account(name=f"{outcome.value} seller", cash_balance=Decimal("100"))
    db_session.add_all([buyer, seller])
    await db_session.flush()
    book = OrderBookService(db_session)

    for price in (Decimal("0.40"), Decimal("0.60")):
        await book.submit_order(
            market.id,
            seller.id,
            OrderSide.SELL,
            outcome,
            OrderType.LIMIT,
            Decimal("10"),
            price,
        )
        await book.submit_order(
            market.id,
            buyer.id,
            OrderSide.BUY,
            outcome,
            OrderType.LIMIT,
            Decimal("10"),
            price,
        )

    position = await db_session.scalar(
        select(Position).where(Position.account_id == buyer.id, Position.market_id == market.id)
    )
    assert position is not None
    assert getattr(position, shares_attr) == Decimal("20.0000")
    assert getattr(position, cost_attr) == Decimal("0.5000")

    await book.submit_order(
        market.id,
        seller.id,
        OrderSide.BUY,
        outcome,
        OrderType.LIMIT,
        Decimal("5"),
        Decimal("0.50"),
    )
    await book.submit_order(
        market.id,
        buyer.id,
        OrderSide.SELL,
        outcome,
        OrderType.LIMIT,
        Decimal("5"),
        Decimal("0.50"),
    )
    await db_session.refresh(position)
    assert getattr(position, shares_attr) == Decimal("15.0000")
    assert getattr(position, cost_attr) == Decimal("0.5000")

    await book.submit_order(
        market.id,
        seller.id,
        OrderSide.BUY,
        outcome,
        OrderType.LIMIT,
        Decimal("20"),
        Decimal("0.50"),
    )
    await book.submit_order(
        market.id,
        buyer.id,
        OrderSide.SELL,
        outcome,
        OrderType.LIMIT,
        Decimal("20"),
        Decimal("0.50"),
    )
    await db_session.refresh(position)
    assert getattr(position, shares_attr) == Decimal("-5.0000")
    assert getattr(position, cost_attr) == Decimal("0.5000")


@pytest.mark.asyncio
async def test_record_fill_caps_stale_match_to_both_orders_remaining_quantity(db_session):
    market = await MarketService(db_session).create_market(
        slug="record-fill-remaining-cap",
        title="Record fill remaining cap",
        question="Does a stale match overfill resting liquidity?",
    )
    buyer = Account(name="Fill-cap buyer", cash_balance=Decimal("100"))
    seller = Account(name="Fill-cap seller", cash_balance=Decimal("100"))
    db_session.add_all([buyer, seller])
    await db_session.flush()
    buy_order = Order(
        market_id=market.id,
        account_id=buyer.id,
        side=OrderSide.BUY,
        outcome=OrderOutcome.YES,
        order_type=OrderType.LIMIT,
        price=Decimal("0.50"),
        quantity=Decimal("5"),
    )
    sell_order = Order(
        market_id=market.id,
        account_id=seller.id,
        side=OrderSide.SELL,
        outcome=OrderOutcome.YES,
        order_type=OrderType.LIMIT,
        price=Decimal("0.50"),
        quantity=Decimal("5"),
        filled_quantity=Decimal("4"),
        status=OrderStatus.PARTIAL,
    )
    db_session.add_all([buy_order, sell_order])
    await db_session.flush()
    match = MatchResult(
        buy_order_id=buy_order.id,
        sell_order_id=sell_order.id,
        outcome=Outcome.YES,
        price=Decimal("0.50"),
        quantity=Decimal("3"),
    )

    book = OrderBookService(db_session)
    await book._record_fill(market.id, match)
    await book._record_fill(market.id, match)
    await db_session.refresh(buy_order)
    await db_session.refresh(sell_order)
    await db_session.refresh(buyer)
    await db_session.refresh(seller)

    fills = (await db_session.scalars(select(Fill).where(Fill.market_id == market.id))).all()
    assert [(fill.price, fill.quantity) for fill in fills] == [
        (Decimal("0.5000"), Decimal("1.0000"))
    ]
    assert buy_order.filled_quantity == Decimal("1.0000")
    assert buy_order.status == OrderStatus.PARTIAL
    assert sell_order.filled_quantity == Decimal("5.0000")
    assert sell_order.status == OrderStatus.FILLED
    assert buyer.cash_balance == Decimal("99.5000")
    assert seller.cash_balance == Decimal("100.5000")
