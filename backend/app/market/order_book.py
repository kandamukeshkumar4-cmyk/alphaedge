"""In-memory CLOB engine — price-time priority for YES outcome contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List
from uuid import UUID

MIN_PRICE = Decimal("0.01")
MAX_PRICE = Decimal("0.99")


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Outcome(str, Enum):
    YES = "yes"
    NO = "no"


@dataclass(order=True)
class BookOrder:
    sort_index: tuple
    order_id: UUID
    account_id: UUID
    side: Side
    outcome: Outcome
    price: Decimal
    remaining: Decimal
    created_seq: int

    @staticmethod
    def bid_sort_key(price: Decimal, seq: int) -> tuple:
        return (-price, seq)

    @staticmethod
    def ask_sort_key(price: Decimal, seq: int) -> tuple:
        return (price, seq)


@dataclass
class MatchResult:
    buy_order_id: UUID
    sell_order_id: UUID
    outcome: Outcome
    price: Decimal
    quantity: Decimal


@dataclass
class OrderBook:
    """Separate bid/ask books per outcome (YES and NO)."""

    market_id: UUID
    _seq: int = 0
    yes_bids: List[BookOrder] = field(default_factory=list)
    yes_asks: List[BookOrder] = field(default_factory=list)
    no_bids: List[BookOrder] = field(default_factory=list)
    no_asks: List[BookOrder] = field(default_factory=list)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _book_for(self, outcome: Outcome, side: Side) -> List[BookOrder]:
        if outcome == Outcome.YES:
            return self.yes_bids if side == Side.BUY else self.yes_asks
        return self.no_bids if side == Side.BUY else self.no_asks

    def _opposite_book(self, outcome: Outcome, side: Side) -> List[BookOrder]:
        opp_side = Side.SELL if side == Side.BUY else Side.BUY
        return self._book_for(outcome, opp_side)

    @staticmethod
    def _insert_sorted(book: List[BookOrder], order: BookOrder) -> None:
        book.append(order)
        book.sort(key=lambda o: o.sort_index)

    def add_limit(
        self,
        order_id: UUID,
        account_id: UUID,
        side: Side,
        outcome: Outcome,
        price: Decimal,
        quantity: Decimal,
    ) -> List[MatchResult]:
        if price < MIN_PRICE or price > MAX_PRICE:
            raise ValueError(f"Price must be between {MIN_PRICE} and {MAX_PRICE}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        matches: List[MatchResult] = []
        remaining = quantity

        while remaining > 0:
            opposite = self._opposite_book(outcome, side)
            if not opposite:
                break
            best = opposite[0]
            if side == Side.BUY and price < best.price:
                break
            if side == Side.SELL and price > best.price:
                break

            fill_qty = min(remaining, best.remaining)
            fill_price = best.price

            if side == Side.BUY:
                buy_id, sell_id = order_id, best.order_id
            else:
                buy_id, sell_id = best.order_id, order_id

            matches.append(
                MatchResult(
                    buy_order_id=buy_id,
                    sell_order_id=sell_id,
                    outcome=outcome,
                    price=fill_price,
                    quantity=fill_qty,
                )
            )
            remaining -= fill_qty
            best.remaining -= fill_qty
            if best.remaining <= 0:
                opposite.pop(0)

        if remaining > 0:
            seq = self._next_seq()
            sort_index = (
                BookOrder.bid_sort_key(price, seq)
                if side == Side.BUY
                else BookOrder.ask_sort_key(price, seq)
            )
            resting = BookOrder(
                sort_index=sort_index,
                order_id=order_id,
                account_id=account_id,
                side=side,
                outcome=outcome,
                price=price,
                remaining=remaining,
                created_seq=seq,
            )
            self._insert_sorted(self._book_for(outcome, side), resting)

        return matches

    def add_market(
        self,
        order_id: UUID,
        account_id: UUID,
        side: Side,
        outcome: Outcome,
        quantity: Decimal,
    ) -> List[MatchResult]:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        opposite = self._opposite_book(outcome, side)
        if not opposite:
            raise ValueError("No liquidity for market order")

        matches: List[MatchResult] = []
        remaining = quantity
        while remaining > 0 and opposite:
            best = opposite[0]
            fill_qty = min(remaining, best.remaining)
            if side == Side.BUY:
                buy_id, sell_id = order_id, best.order_id
            else:
                buy_id, sell_id = best.order_id, order_id

            matches.append(
                MatchResult(
                    buy_order_id=buy_id,
                    sell_order_id=sell_id,
                    outcome=outcome,
                    price=best.price,
                    quantity=fill_qty,
                )
            )
            remaining -= fill_qty
            best.remaining -= fill_qty
            if best.remaining <= 0:
                opposite.pop(0)

        return matches

    def quote_market(
        self,
        side: Side,
        outcome: Outcome,
        quantity: Decimal,
    ) -> List[tuple[Decimal, Decimal]]:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        remaining = quantity
        levels: List[tuple[Decimal, Decimal]] = []
        for order in self._opposite_book(outcome, side):
            fill_qty = min(remaining, order.remaining)
            levels.append((order.price, fill_qty))
            remaining -= fill_qty
            if remaining <= 0:
                break
        return levels

    def cancel(self, order_id: UUID) -> bool:
        removed = False
        for book in (self.yes_bids, self.yes_asks, self.no_bids, self.no_asks):
            original_len = len(book)
            book[:] = [order for order in book if order.order_id != order_id]
            removed = removed or len(book) != original_len
        return removed

    def l2_snapshot(self, depth: int = 10) -> dict:
        def aggregate(book: List[BookOrder], reverse: bool = False) -> list:
            levels: dict[Decimal, Decimal] = {}
            for o in book:
                levels[o.price] = levels.get(o.price, Decimal("0")) + o.remaining
            items = sorted(levels.items(), key=lambda x: x[0], reverse=reverse)
            return [{"price": float(p), "size": float(s)} for p, s in items[:depth]]

        return {
            "yes": {"bids": aggregate(self.yes_bids, True), "asks": aggregate(self.yes_asks)},
            "no": {"bids": aggregate(self.no_bids, True), "asks": aggregate(self.no_asks)},
        }
