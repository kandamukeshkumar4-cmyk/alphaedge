"""Canonical integration test: Lakers vs Celtics — matching + P&L on resolution."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models import Account, OrderOutcome, OrderSide, OrderType
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

LAKERS_SLUG = "nba-2025-01-15-lal-bos"
LOCK_AT = datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_lakers_celtics_matching_and_pnl(db_session):
  """Two accounts trade YES; Lakers win (YES) settles at $1/share."""
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug=LAKERS_SLUG,
      title="Lakers vs Celtics",
      question="Will the Lakers win?",
      lock_at=LOCK_AT,
  )

  maker = Account(name="Maker", cash_balance=Decimal("5000"))
  taker = Account(name="Taker", cash_balance=Decimal("5000"))
  db_session.add(maker)
  db_session.add(taker)
  await db_session.flush()

  # Maker posts YES ask @ 0.55
  await obs.submit_order(
      market.id,
      maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  # Taker buys YES @ 0.55 (crosses)
  taker_order = await obs.submit_order(
      market.id,
      taker.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  assert taker_order.filled_quantity == Decimal("100")
  assert taker_order.status.value == "filled"

  await market_svc.lock_market(market.id)
  resolved = await market_svc.resolve_market(market.id, OrderOutcome.YES)
  assert resolved.winning_outcome == OrderOutcome.YES

  await db_session.refresh(taker)
  await db_session.refresh(maker)

  # Taker holds 100 YES @ $1 = +$100 payout minus $55 cost = net +$45 on settlement credit
  # Cash: started 5000, paid 55 for shares, received 100 settlement = 5045
  assert taker.cash_balance == Decimal("5045.00") or taker.cash_balance == Decimal("5045")

  # Maker sold YES: received 55, no winning shares
  assert maker.cash_balance >= Decimal("5055")


@pytest.mark.asyncio
async def test_order_book_price_time_priority():
  """Unit-style: earlier order at same price has priority."""
  from app.market.order_book import OrderBook, Outcome, Side

  book = OrderBook(market_id=uuid4())
  aid1, aid2 = uuid4(), uuid4()
  oid1, oid2, oid3 = uuid4(), uuid4(), uuid4()

  book.add_limit(oid1, aid1, Side.SELL, Outcome.YES, Decimal("0.50"), Decimal("50"))
  book.add_limit(oid2, aid2, Side.SELL, Outcome.YES, Decimal("0.50"), Decimal("50"))

  matches = book.add_limit(oid3, uuid4(), Side.BUY, Outcome.YES, Decimal("0.50"), Decimal("75"))
  assert len(matches) == 2
  assert matches[0].quantity == Decimal("50")
  assert matches[0].sell_order_id == oid1
  assert matches[1].sell_order_id == oid2
  assert matches[1].quantity == Decimal("25")
