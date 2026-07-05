"""Polymarket data-api connector (public REST, no auth).

Provides leaderboards, wallet positions, and wallet trades for the whale tracker.
Pure normalizers turn raw payloads into typed rows so tests run against fixtures
with no network. Read-only: no keys, no order path.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.data.connectors.http import JsonConnectorClient

SOURCE = "polymarket.data-api"
DEFAULT_BASE_URL = "https://data-api.polymarket.com"
# The leaderboard lives on a separate host; data-api has no /leaderboard route
# (verified live 2026-07-02: data-api/leaderboard -> 404, lb-api/profit -> 200).
DEFAULT_LEADERBOARD_BASE_URL = "https://lb-api.polymarket.com"


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


@dataclass(frozen=True)
class LeaderboardEntry:
    wallet_address: str
    pnl: Decimal
    volume: Decimal


@dataclass(frozen=True)
class WalletPositionRow:
    wallet_address: str
    market_id: str
    market_slug: str
    outcome: str  # "YES" / "NO"
    size: Decimal
    avg_price: Decimal


@dataclass(frozen=True)
class WalletTrade:
    market_id: str
    outcome: str
    side: str  # BUY / SELL
    price: Decimal
    size: Decimal
    pnl: Decimal
    resolved: bool


def _wallet_of(row: dict[str, Any]) -> str:
    return str(
        row.get("proxyWallet")
        or row.get("wallet")
        or row.get("user")
        or row.get("address")
        or ""
    ).lower()


def _outcome_of(row: dict[str, Any]) -> str:
    raw = str(row.get("outcome") or row.get("tokenOutcome") or row.get("asset") or "").strip()
    upper = raw.upper()
    if upper in {"YES", "NO"}:
        return upper
    # Some payloads use outcomeIndex 0=YES, 1=NO
    idx = row.get("outcomeIndex")
    if idx is not None:
        try:
            return "YES" if int(idx) == 0 else "NO"
        except (TypeError, ValueError):
            pass
    return upper or "YES"


def normalize_leaderboard(payload: Any) -> list[LeaderboardEntry]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out: list[LeaderboardEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        wallet = _wallet_of(row)
        if not wallet:
            continue
        out.append(
            LeaderboardEntry(
                wallet_address=wallet,
                pnl=_dec(
                    row.get("pnl")
                    or row.get("profit")
                    or row.get("realizedPnl")
                    or row.get("amount")
                ),
                volume=_dec(row.get("volume") or row.get("vol")),
            )
        )
    return out


def normalize_positions(payload: Any, wallet_address: str) -> list[WalletPositionRow]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    wallet = wallet_address.lower()
    out: list[WalletPositionRow] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        size = _dec(row.get("size") or row.get("shares") or row.get("quantity"))
        if size <= 0:
            continue
        market_id = str(
            row.get("conditionId") or row.get("market") or row.get("marketId") or ""
        )
        slug = str(row.get("slug") or row.get("marketSlug") or market_id)
        out.append(
            WalletPositionRow(
                wallet_address=wallet,
                market_id=market_id,
                market_slug=slug,
                outcome=_outcome_of(row),
                size=size,
                avg_price=_dec(row.get("avgPrice") or row.get("averagePrice") or row.get("price")),
            )
        )
    return out


def normalize_trades(payload: Any) -> list[WalletTrade]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out: list[WalletTrade] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            WalletTrade(
                market_id=str(row.get("conditionId") or row.get("market") or ""),
                outcome=_outcome_of(row),
                side=str(row.get("side") or "").upper(),
                price=_dec(row.get("price")),
                size=_dec(row.get("size") or row.get("shares")),
                pnl=_dec(row.get("pnl") or row.get("realizedPnl")),
                resolved=bool(row.get("resolved") or row.get("redeemed") or row.get("settled")),
            )
        )
    return out


def normalize_closed_positions(payload: Any) -> list[WalletTrade]:
    """Closed positions carry realizedPnl and are resolved by definition.

    Live /trades rows have no pnl/resolved fields (verified 2026-07-02), so whale
    qualification derives WalletStats from /closed-positions instead.
    """
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out: list[WalletTrade] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            WalletTrade(
                market_id=str(row.get("conditionId") or row.get("market") or ""),
                outcome=_outcome_of(row),
                side="BUY",
                price=_dec(row.get("avgPrice") or row.get("price")),
                size=_dec(row.get("totalBought") or row.get("size")),
                pnl=_dec(row.get("realizedPnl") or row.get("pnl")),
                resolved=True,
            )
        )
    return out


class PolymarketDataApiConnector:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        leaderboard_base_url: str = DEFAULT_LEADERBOARD_BASE_URL,
        leaderboard_client: httpx.Client | None = None,
    ) -> None:
        self.http = JsonConnectorClient(base_url=base_url, client=client)
        self.leaderboard_http = JsonConnectorClient(
            base_url=leaderboard_base_url, client=leaderboard_client
        )

    def fetch_leaderboard(
        self, *, window: str = "all", limit: int = 200
    ) -> list[LeaderboardEntry]:
        payload = self.leaderboard_http.get_json(
            "/profit", params={"window": window, "limit": str(limit)}
        )
        return normalize_leaderboard(payload)

    def fetch_positions(self, user: str) -> list[WalletPositionRow]:
        payload = self.http.get_json("/positions", params={"user": user})
        return normalize_positions(payload, user)

    def fetch_trades(self, user: str, *, limit: int = 500) -> list[WalletTrade]:
        payload = self.http.get_json(
            "/trades", params={"user": user, "limit": str(limit)}
        )
        return normalize_trades(payload)

    def fetch_closed_positions(self, user: str, *, limit: int = 500) -> list[WalletTrade]:
        # The API caps each page at 50 rows (verified live); paginate via offset.
        page_size = 50
        out: list[WalletTrade] = []
        offset = 0
        while len(out) < limit:
            payload = self.http.get_json(
                "/closed-positions",
                params={"user": user, "limit": str(page_size), "offset": str(offset)},
            )
            rows = normalize_closed_positions(payload)
            out.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size
        return out[:limit]
