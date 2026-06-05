from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx


MONEY = Decimal("0.0001")


@dataclass(frozen=True)
class OnchainReadOnlyConnector:
    polygon_rpc_url: str
    polymarket_subgraph_url: str
    client: httpx.Client | None = None

    def fetch_wallet_positions(
        self,
        wallet_address: str,
        *,
        market_prices: dict[tuple[str, str], Decimal] | None = None,
    ) -> list[OnchainWalletPosition]:
        payload = self._fetch_wallet_fill_payload(wallet_address)
        fills = normalize_polymarket_fills(payload, wallet_address)
        return compute_wallet_positions(fills, market_prices=market_prices or {})

    def _fetch_wallet_fill_payload(self, wallet_address: str) -> dict[str, Any]:
        body = {
            "query": """
            query WalletFills($wallet: String!) {
              orderFilleds(where: { wallet: $wallet }, orderBy: timestamp, orderDirection: asc) {
                id
                transactionHash
                timestamp
                wallet
                market
                outcome
                side
                price
                quantity
              }
            }
            """,
            "variables": {"wallet": wallet_address.lower()},
        }
        if self.client is not None:
            response = self.client.post(self.polymarket_subgraph_url, json=body)
            response.raise_for_status()
            payload = response.json()
        else:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(self.polymarket_subgraph_url, json=body)
                response.raise_for_status()
                payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Polymarket subgraph returned a non-object payload")
        return payload


@dataclass(frozen=True)
class OnchainFill:
    fill_id: str
    transaction_hash: str
    wallet_address: str
    market_id: str
    outcome: str
    side: str
    price: Decimal
    quantity: Decimal
    timestamp: datetime | None = None


@dataclass(frozen=True)
class OnchainWalletPosition:
    wallet_address: str
    market_id: str
    outcome: str
    side: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    roi: Decimal
    hit_rate: Decimal
    total_trades: int


def normalize_polymarket_fills(payload: dict[str, Any], wallet_address: str) -> list[OnchainFill]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Polymarket subgraph payload does not include data")
    raw_fills = data.get("orderFilleds") or data.get("fills") or []
    if not isinstance(raw_fills, list):
        raise ValueError("Polymarket subgraph fills payload is not a list")

    wallet = wallet_address.lower()
    fills: list[OnchainFill] = []
    for raw in raw_fills:
        if not isinstance(raw, dict):
            continue
        fill_wallet = str(raw.get("wallet") or raw.get("user") or wallet).lower()
        if fill_wallet != wallet:
            continue
        fills.append(
            OnchainFill(
                fill_id=str(raw.get("id") or ""),
                transaction_hash=str(raw.get("transactionHash") or raw.get("txHash") or ""),
                wallet_address=fill_wallet,
                market_id=str(raw.get("market") or raw.get("marketId") or raw.get("conditionId")),
                outcome=str(raw.get("outcome") or raw.get("tokenOutcome") or "").upper(),
                side=str(raw.get("side") or "").upper(),
                price=_decimal(raw.get("price")),
                quantity=_decimal(raw.get("quantity") or raw.get("size") or raw.get("amount")),
                timestamp=_timestamp(raw.get("timestamp")),
            )
        )
    return fills


def compute_wallet_positions(
    fills: list[OnchainFill],
    *,
    market_prices: dict[tuple[str, str], Decimal],
) -> list[OnchainWalletPosition]:
    states: dict[tuple[str, str], _PositionState] = {}
    for fill in sorted(fills, key=lambda item: item.timestamp or datetime.min.replace(tzinfo=UTC)):
        key = (fill.market_id, fill.outcome)
        state = states.setdefault(key, _PositionState(wallet_address=fill.wallet_address))
        if fill.side == "BUY":
            state.buy(fill.price, fill.quantity)
        elif fill.side == "SELL":
            state.sell(fill.price, fill.quantity)

    positions: list[OnchainWalletPosition] = []
    for (market_id, outcome), state in states.items():
        current_price = _lookup_price(market_prices, market_id, outcome)
        average_price = state.average_price
        unrealized = (
            _money((current_price - average_price) * state.quantity)
            if current_price is not None and state.quantity > 0
            else Decimal("0.0000")
        )
        total_pnl = _money(state.realized_pnl + unrealized)
        roi = _money(total_pnl / state.total_buy_cost) if state.total_buy_cost > 0 else Decimal("0.0000")
        positions.append(
            OnchainWalletPosition(
                wallet_address=state.wallet_address,
                market_id=market_id,
                outcome=outcome,
                side=outcome if state.quantity > 0 else "FLAT",
                quantity=_money(state.quantity),
                average_price=average_price,
                current_price=current_price,
                realized_pnl=_money(state.realized_pnl),
                unrealized_pnl=unrealized,
                total_pnl=total_pnl,
                roi=roi,
                hit_rate=Decimal("1.0000") if total_pnl > 0 else Decimal("0.0000"),
                total_trades=state.total_trades,
            )
        )
    return [position for position in positions if position.quantity > 0]


@dataclass
class _PositionState:
    wallet_address: str
    quantity: Decimal = Decimal("0")
    cost_basis: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    total_buy_cost: Decimal = Decimal("0")
    total_trades: int = 0

    @property
    def average_price(self) -> Decimal:
        if self.quantity <= 0:
            return Decimal("0.0000")
        return _money(self.cost_basis / self.quantity)

    def buy(self, price: Decimal, quantity: Decimal) -> None:
        self.quantity += quantity
        cost = price * quantity
        self.cost_basis += cost
        self.total_buy_cost += cost
        self.total_trades += 1

    def sell(self, price: Decimal, quantity: Decimal) -> None:
        if self.quantity <= 0:
            self.realized_pnl += price * quantity
            self.total_trades += 1
            return
        closed_quantity = min(quantity, self.quantity)
        average = self.cost_basis / self.quantity
        self.realized_pnl += (price - average) * closed_quantity
        self.cost_basis -= average * closed_quantity
        self.quantity -= closed_quantity
        self.total_trades += 1


def _lookup_price(
    market_prices: dict[tuple[str, str], Decimal],
    market_id: str,
    outcome: str,
) -> Decimal | None:
    for key in ((market_id, outcome), (market_id.lower(), outcome.lower())):
        if key in market_prices:
            return _money(market_prices[key])
    return None


def _decimal(value: object) -> Decimal:
    if value is None:
        raise ValueError("Polymarket fill is missing a numeric value")
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=UTC)
    text = str(value)
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=UTC)
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
