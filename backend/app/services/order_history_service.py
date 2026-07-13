"""Cursor-paginated history for the risk-gated CLOB order ledger."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Fill, Market, Order, OrderStatus
from app.schemas.market import (
    OrderFillBreakdownResponse,
    OrderHistoryItemResponse,
    OrderHistoryPageResponse,
)


class InvalidOrderHistoryCursor(ValueError):
    """Raised when an opaque order-history cursor cannot be decoded."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _encode_cursor(
    created_at: datetime,
    order_id: UUID,
    *,
    database_sort_key: str | None = None,
) -> str:
    cursor_payload = {
        "created_at": _as_utc(created_at).isoformat(),
        "order_id": str(order_id),
    }
    if database_sort_key is not None:
        cursor_payload["database_sort_key"] = database_sort_key
    payload = json.dumps(cursor_payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID, str | None]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        created_at = datetime.fromisoformat(payload["created_at"])
        order_id = UUID(payload["order_id"])
        database_sort_key = payload.get("database_sort_key")
        if database_sort_key is not None and not isinstance(database_sort_key, str):
            raise TypeError
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise InvalidOrderHistoryCursor("Invalid order history cursor") from exc
    return _as_utc(created_at), order_id, database_sort_key


class OrderHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_orders(
        self,
        account_id: UUID,
        *,
        status: OrderStatus | None = None,
        market_slug: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> OrderHistoryPageResponse:
        """Return a stable newest-first page with each order's fill rows."""
        bounded_limit = min(max(limit, 1), 100)
        bind = self.session.get_bind()
        sqlite_sort = bind.dialect.name == "sqlite"
        created_at_key = (
            func.strftime("%Y-%m-%d %H:%M:%f", Order.created_at)
            if sqlite_sort
            else Order.created_at
        ).label("order_history_created_at_key")
        statement = (
            select(Order, Market, created_at_key)
            .join(Market, Market.id == Order.market_id)
            .where(Order.account_id == account_id)
        )
        if status is not None:
            statement = statement.where(Order.status == status)
        if market_slug is not None:
            statement = statement.where(Market.slug == market_slug)
        if cursor is not None:
            cursor_created_at, cursor_order_id, database_sort_key = _decode_cursor(cursor)
            cursor_created_at_key: datetime | str = cursor_created_at
            if sqlite_sort:
                # SQLite's strftime key can round fractional seconds. Persist
                # the exact DB-produced key in the opaque cursor and use the
                # same expression for ordering and comparison, so neither a
                # precision mismatch nor same-millisecond rows repeat/skip.
                if database_sort_key is None:
                    raise InvalidOrderHistoryCursor("Invalid order history cursor")
                cursor_created_at_key = database_sort_key
            statement = statement.where(
                or_(
                    created_at_key < cursor_created_at_key,
                    and_(
                        created_at_key == cursor_created_at_key,
                        Order.id < cursor_order_id,
                    ),
                )
            )

        rows = (
            await self.session.execute(
                statement
                .order_by(created_at_key.desc(), Order.id.desc())
                .limit(bounded_limit + 1)
            )
        ).all()
        has_more = len(rows) > bounded_limit
        page_rows = rows[:bounded_limit]

        order_ids = [order.id for order, _market, _created_at_key in page_rows]
        fills_by_order: dict[UUID, list[Fill]] = {order_id: [] for order_id in order_ids}
        if order_ids:
            fills = list(
                (
                    await self.session.scalars(
                        select(Fill)
                        .where(
                            or_(
                                Fill.buy_order_id.in_(order_ids),
                                Fill.sell_order_id.in_(order_ids),
                            )
                        )
                        .order_by(Fill.created_at, Fill.id)
                    )
                ).all()
            )
            for fill in fills:
                if fill.buy_order_id in fills_by_order:
                    fills_by_order[fill.buy_order_id].append(fill)
                if fill.sell_order_id in fills_by_order:
                    fills_by_order[fill.sell_order_id].append(fill)

        items: list[OrderHistoryItemResponse] = []
        for order, market, _created_at_key in page_rows:
            order_fills = fills_by_order[order.id]
            raw_filled_notional = sum(
                (fill.price * fill.quantity for fill in order_fills),
                start=Decimal("0"),
            )
            filled_notional = raw_filled_notional.quantize(Decimal("0.0001"))
            average_fill_price = None
            if order.filled_quantity > 0:
                average_fill_price = (
                    raw_filled_notional / order.filled_quantity
                ).quantize(Decimal("0.0001"))
            items.append(
                OrderHistoryItemResponse(
                    id=order.id,
                    market_id=order.market_id,
                    market_slug=market.slug,
                    market_title=market.title,
                    side=order.side,
                    outcome=order.outcome,
                    order_type=order.order_type,
                    price=order.price,
                    quantity=order.quantity,
                    filled_quantity=order.filled_quantity,
                    remaining_quantity=order.quantity - order.filled_quantity,
                    filled_notional=filled_notional,
                    average_fill_price=average_fill_price,
                    status=order.status,
                    expires_at=order.expires_at,
                    created_at=order.created_at,
                    fills=[
                        OrderFillBreakdownResponse(
                            id=fill.id,
                            price=fill.price,
                            quantity=fill.quantity,
                            created_at=fill.created_at,
                        )
                        for fill in order_fills
                    ],
                )
            )

        next_cursor = None
        if has_more and page_rows:
            last_order, _last_market, last_created_at_key = page_rows[-1]
            next_cursor = _encode_cursor(
                last_order.created_at,
                last_order.id,
                database_sort_key=str(last_created_at_key) if sqlite_sort else None,
            )
        return OrderHistoryPageResponse(items=items, next_cursor=next_cursor)
