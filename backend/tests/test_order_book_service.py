from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Account, LedgerEntry, LedgerEntryType, OrderOutcome, OrderSide, OrderType
from app.services.ledger_service import LedgerService
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService


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
