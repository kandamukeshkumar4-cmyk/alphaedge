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

from app.db.models import Fill, Market, OddsSnapshot, WalletPositionSnapshot
from app.signals.smart_money import WhalePositionState, diff_whale_positions

# A "large" position change (in shares) that qualifies as whale activity.
_WHALE_MIN_SIZE_CHANGE = Decimal("100")

# Ideas adapted (clean-room) from vendor-study MCP READMEs — see docs/ATTRIBUTIONS.md.
# Depth skew / holders concentration / trade intensity; never paste vendor source.


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


async def get_depth_skew(
    session: AsyncSession,
    slug: str,
    *,
    connector: Any | None = None,
    depth: int = 5,
) -> dict[str, Any]:
    """Bid vs ask size imbalance from the L2 book (MCP order-book idea, clean-room).

    ``skew`` in [-1, 1]: positive = more bid size (buy pressure), negative = ask-heavy.
    """
    name = "get_depth_skew"
    try:
        book = await get_order_book_summary(
            session, slug, connector=connector, depth=depth
        )
        if book.get("error"):
            return {"error": book["error"], "tool": name}
        yes = (book.get("depth") or {}).get("yes") or {}
        bids = yes.get("bids") or []
        asks = yes.get("asks") or []

        def _size(levels: list[Any]) -> float:
            total = 0.0
            for lvl in levels:
                if isinstance(lvl, dict):
                    total += float(lvl.get("size") or lvl.get("quantity") or 0)
            return total

        bid_size = _size(bids)
        ask_size = _size(asks)
        denom = bid_size + ask_size
        skew = round((bid_size - ask_size) / denom, 4) if denom > 0 else 0.0
        return {
            "tool": name,
            "slug": slug,
            "bid_size": round(bid_size, 4),
            "ask_size": round(ask_size, 4),
            "skew": skew,
            "levels": min(len(bids), len(asks), depth),
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


async def get_whale_concentration(
    session: AsyncSession,
    slug: str,
    *,
    top_n: int = 5,
) -> dict[str, Any]:
    """Share of open interest held by the top-N wallets (holders idea, clean-room)."""
    name = "get_whale_concentration"
    try:
        rows = (
            await session.execute(
                select(WalletPositionSnapshot)
                .where(WalletPositionSnapshot.market_slug == slug)
                .order_by(WalletPositionSnapshot.captured_at.desc())
                .limit(500)
            )
        ).scalars().all()
        # Latest snapshot per wallet (rows are newest-first).
        latest: dict[str, Decimal] = {}
        for row in rows:
            if row.wallet_address in latest:
                continue
            latest[row.wallet_address] = abs(Decimal(row.size or 0))

        sizes = sorted(latest.values(), reverse=True)
        total = sum(sizes, Decimal("0"))
        top = sizes[: max(1, top_n)]
        top_sum = sum(top, Decimal("0"))
        pct = float(top_sum / total) if total > 0 else 0.0
        return {
            "tool": name,
            "slug": slug,
            "wallet_count": len(sizes),
            "top_n": top_n,
            "top_share": round(pct, 4),
            "total_size": float(total),
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


async def get_trade_intensity(
    session: AsyncSession,
    slug: str,
    hours: int = 24,
) -> dict[str, Any]:
    """Paper fill count + notional in a window (recent-trades idea, clean-room)."""
    name = "get_trade_intensity"
    try:
        market = await session.scalar(select(Market).where(Market.slug == slug))
        if market is None:
            return {
                "tool": name,
                "slug": slug,
                "hours": hours,
                "fill_count": 0,
                "notional": 0.0,
                "fills_per_hour": 0.0,
            }
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        fills = (
            await session.execute(
                select(Fill)
                .where(Fill.market_id == market.id, Fill.created_at >= cutoff)
                .order_by(Fill.created_at.desc())
                .limit(500)
            )
        ).scalars().all()
        notional = sum(
            (Decimal(f.price) * Decimal(f.quantity) for f in fills),
            Decimal("0"),
        )
        count = len(fills)
        per_hour = round(count / max(hours, 1), 4)
        return {
            "tool": name,
            "slug": slug,
            "hours": hours,
            "fill_count": count,
            "notional": float(round(notional, 4)),
            "fills_per_hour": per_hour,
        }
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return {"error": str(exc), "tool": name}


def summarize_tools_used(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact per-tool summary (name + key figures) for the research brief payload."""
    ob = result.get("order_book") or {}
    ph = result.get("price_history") or {}
    wh = result.get("whale_activity") or {}
    ds = result.get("depth_skew") or {}
    wc = result.get("whale_concentration") or {}
    ti = result.get("trade_intensity") or {}
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
        {
            "tool": "get_depth_skew",
            "skew": ds.get("skew"),
            "error": ds.get("error"),
        },
        {
            "tool": "get_whale_concentration",
            "top_share": wc.get("top_share"),
            "error": wc.get("error"),
        },
        {
            "tool": "get_trade_intensity",
            "fill_count": ti.get("fill_count"),
            "fills_per_hour": ti.get("fills_per_hour"),
            "error": ti.get("error"),
        },
    ]


async def gather_market_tools(
    session: AsyncSession,
    slug: str,
    *,
    hours: int = 24,
    connector: Any | None = None,
) -> dict[str, Any]:
    """Run market-data tools CONCURRENTLY and return their combined dict.

    Never raises: each tool already returns an error dict on failure, and the gather
    itself is failure-isolated so one slow/broken tool cannot break the others.
    """
    try:
        (
            order_book,
            price_history,
            whale_activity,
            depth_skew,
            whale_concentration,
            trade_intensity,
        ) = await asyncio.gather(
            get_order_book_summary(session, slug, connector=connector),
            get_price_history(session, slug, hours=hours),
            get_whale_activity(session, slug),
            get_depth_skew(session, slug, connector=connector),
            get_whale_concentration(session, slug),
            get_trade_intensity(session, slug, hours=hours),
        )
    except Exception as exc:  # noqa: BLE001 - defensive; gather should not raise
        err = {"error": str(exc)}
        order_book = {**err, "tool": "get_order_book_summary"}
        price_history = {**err, "tool": "get_price_history"}
        whale_activity = {**err, "tool": "get_whale_activity"}
        depth_skew = {**err, "tool": "get_depth_skew"}
        whale_concentration = {**err, "tool": "get_whale_concentration"}
        trade_intensity = {**err, "tool": "get_trade_intensity"}

    result: dict[str, Any] = {
        "order_book": order_book,
        "price_history": price_history,
        "whale_activity": whale_activity,
        "depth_skew": depth_skew,
        "whale_concentration": whale_concentration,
        "trade_intensity": trade_intensity,
    }
    result["tools_used"] = summarize_tools_used(result)
    return result
