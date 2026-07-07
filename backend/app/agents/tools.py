"""Native market-data tool nodes for the agent graph (report §6 — MCP capability).

The technical report calls for MCP servers (polymarket-agents, PolyMarket-MCP)
exposed as tool nodes. Running external MCP server processes is not viable on the
free-tier deploy, so the CAPABILITY is implemented natively here: async tools that
give reasoning agents on-demand market data from the connectors/tables that already
exist in ``app/data`` and ``app/db``.

Contract: every tool returns a compact ``dict`` and NEVER raises. On any failure it
returns ``{"error": "...", "tool": <name>}`` so a partial tool failure degrades the
agent context gracefully instead of breaking a run.

Read-only: these tools observe market state. They never touch RiskService or
OrderBookService's write path — only the read-only L2 snapshot.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, OddsSnapshot, WalletPositionSnapshot
from app.signals.smart_money import WhalePositionState, diff_whale_positions

# A "large" position change (in shares) that qualifies as whale activity.
_WHALE_MIN_SIZE_CHANGE = Decimal("100")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def get_order_book_summary(
    session: AsyncSession,
    slug: str,
    *,
    connector: Any | None = None,
    depth: int = 5,
) -> dict[str, Any]:
    """Best bid/ask, spread, and top-``depth`` depth per side for a market.

    Local markets are read from the in-process CLOB (OrderBookService.get_l2).
    Mirrored live markets (no local row) fall back to ``connector`` when supplied.
    """
    name = "get_order_book_summary"
    try:
        market = await session.scalar(select(Market).where(Market.slug == slug))
        if market is None:
            if connector is not None:
                return _summary_from_connector(connector, slug, name)
            return {"error": f"market '{slug}' not found", "tool": name}

        from app.services.order_book_service import OrderBookService

        l2 = await OrderBookService(session).get_l2(market.id, depth=depth)
        yes = l2.get("yes", {}) if isinstance(l2, dict) else {}
        bids = yes.get("bids", []) or []
        asks = yes.get("asks", []) or []
        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        spread = (
            round(best_ask - best_bid, 4)
            if best_bid is not None and best_ask is not None
            else None
        )
        return {
            "tool": name,
            "slug": slug,
            "source": "local_clob",
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "depth": {
                "yes": {"bids": bids[:depth], "asks": asks[:depth]},
                "no": {
                    "bids": (l2.get("no", {}).get("bids", []) or [])[:depth],
                    "asks": (l2.get("no", {}).get("asks", []) or [])[:depth],
                },
            },
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


def _summary_from_connector(connector: Any, slug: str, name: str) -> dict[str, Any]:
    """Best-effort bid/ask for a mirrored live market via a Polymarket-style connector."""
    try:
        snapshot = connector.fetch_market_snapshot(slug)
        meta = getattr(snapshot, "metadata", {}) or {}
        best_bid = meta.get("yes_bid")
        best_ask = meta.get("executable_yes_ask")
        spread = (
            round(best_ask - best_bid, 4)
            if isinstance(best_bid, (int, float)) and isinstance(best_ask, (int, float))
            else None
        )
        return {
            "tool": name,
            "slug": slug,
            "source": "connector",
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "implied_yes": getattr(snapshot, "implied_yes", None),
            "depth": {"yes": {"bids": [], "asks": []}, "no": {"bids": [], "asks": []}},
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


async def get_price_history(
    session: AsyncSession,
    slug: str,
    hours: int = 24,
) -> dict[str, Any]:
    """Recent implied-YES ticks for a market from the odds-snapshot history table."""
    name = "get_price_history"
    try:
        rows = (
            await session.execute(
                select(OddsSnapshot.captured_at, OddsSnapshot.implied_yes)
                .where(OddsSnapshot.market_slug == slug)
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(500)
            )
        ).all()
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        ticks = [
            {"t": _aware(captured).isoformat(), "implied_yes": float(implied)}
            for captured, implied in rows
            if captured is not None and _aware(captured) >= cutoff
        ]
        ticks.reverse()  # oldest -> newest
        prices = [t["implied_yes"] for t in ticks]
        return {
            "tool": name,
            "slug": slug,
            "hours": hours,
            "points": len(ticks),
            "first": prices[0] if prices else None,
            "last": prices[-1] if prices else None,
            "high": max(prices) if prices else None,
            "low": min(prices) if prices else None,
            "change": round(prices[-1] - prices[0], 4) if len(prices) >= 2 else 0.0,
            "ticks": ticks[-50:],
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


async def get_whale_activity(
    session: AsyncSession,
    slug: str,
    *,
    min_size_change: Decimal = _WHALE_MIN_SIZE_CHANGE,
) -> dict[str, Any]:
    """Recent large position changes for a market.

    Reuses ``smart_money.diff_whale_positions`` (no duplicated diff logic): the two
    most recent position snapshots per wallet are diffed and only moves >=
    ``min_size_change`` shares are reported.
    """
    name = "get_whale_activity"
    try:
        rows = (
            await session.execute(
                select(WalletPositionSnapshot)
                .where(WalletPositionSnapshot.market_slug == slug)
                .order_by(WalletPositionSnapshot.captured_at.asc())
            )
        ).scalars().all()

        by_wallet: dict[str, list[WalletPositionSnapshot]] = defaultdict(list)
        for row in rows:
            by_wallet[row.wallet_address].append(row)

        deltas: list[dict[str, Any]] = []
        for wallet, snaps in by_wallet.items():
            curr_snap = snaps[-1]
            prev_snap = snaps[-2] if len(snaps) >= 2 else None
            prev_state = (
                [WhalePositionState(prev_snap.market_slug, prev_snap.outcome, prev_snap.size)]
                if prev_snap is not None
                else []
            )
            curr_state = [
                WhalePositionState(curr_snap.market_slug, curr_snap.outcome, curr_snap.size)
            ]
            for d in diff_whale_positions(
                prev_state, curr_state, min_size_change=min_size_change
            ):
                deltas.append(
                    {
                        "wallet": f"{wallet[:8]}…",
                        "action": d.action.value,
                        "outcome": d.outcome,
                        "direction": d.direction,
                        "size_change": float(d.size_change),
                    }
                )

        deltas.sort(key=lambda d: d["size_change"], reverse=True)
        return {
            "tool": name,
            "slug": slug,
            "whale_count": len(deltas),
            "deltas": deltas[:10],
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


def summarize_tools_used(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact per-tool summary (name + key figures) for the research brief payload."""
    ob = result.get("order_book") or {}
    ph = result.get("price_history") or {}
    wh = result.get("whale_activity") or {}
    return [
        {
            "tool": "get_order_book_summary",
            "spread": ob.get("spread"),
            "best_bid": ob.get("best_bid"),
            "best_ask": ob.get("best_ask"),
            "error": ob.get("error"),
        },
        {
            "tool": "get_price_history",
            "points": ph.get("points"),
            "last": ph.get("last"),
            "error": ph.get("error"),
        },
        {
            "tool": "get_whale_activity",
            "whale_count": wh.get("whale_count"),
            "error": wh.get("error"),
        },
    ]


async def gather_market_tools(
    session: AsyncSession,
    slug: str,
    *,
    hours: int = 24,
    connector: Any | None = None,
) -> dict[str, Any]:
    """Run all three market-data tools CONCURRENTLY and return their combined dict.

    Never raises: each tool already returns an error dict on failure, and the gather
    itself is failure-isolated so one slow/broken tool cannot break the others.
    """
    try:
        order_book, price_history, whale_activity = await asyncio.gather(
            get_order_book_summary(session, slug, connector=connector),
            get_price_history(session, slug, hours=hours),
            get_whale_activity(session, slug),
        )
    except Exception as exc:  # noqa: BLE001 - defensive; gather should not raise
        err = {"error": str(exc)}
        order_book = {**err, "tool": "get_order_book_summary"}
        price_history = {**err, "tool": "get_price_history"}
        whale_activity = {**err, "tool": "get_whale_activity"}

    result: dict[str, Any] = {
        "order_book": order_book,
        "price_history": price_history,
        "whale_activity": whale_activity,
    }
    result["tools_used"] = summarize_tools_used(result)
    return result
