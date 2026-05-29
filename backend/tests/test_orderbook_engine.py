from decimal import Decimal
from uuid import uuid4

from app.market.order_book import OrderBook, Outcome, Side


def test_limit_order_resting_book():
    book = OrderBook(market_id=uuid4())
    oid = uuid4()
    matches = book.add_limit(
        oid, uuid4(), Side.BUY, Outcome.YES, Decimal("0.45"), Decimal("10")
    )
    assert matches == []
    snap = book.l2_snapshot()
    assert snap["yes"]["bids"][0]["price"] == 0.45


def test_invalid_price_rejected():
    book = OrderBook(market_id=uuid4())
    try:
        book.add_limit(uuid4(), uuid4(), Side.BUY, Outcome.YES, Decimal("1.50"), Decimal("1"))
        assert False, "Should raise"
    except ValueError:
        pass
