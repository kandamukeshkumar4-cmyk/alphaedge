"""M02 — Shareable compact market snapshot (Loop V8).

``GET /api/v1/markets/{slug}/share-snapshot`` — a SMALL, read-only intelligence
snapshot for one market, sized for an external share card (the frontend `/s/[slug]`
page):

* `title` + current `yes_price`;
* `edge` — the model-vs-market one-liner numbers `{model_p, market_p, edge}`;
* `top_signal` — the most recent alert-family signal (family + H03 citation) or
  `null`;
* `arb_matched` — whether a cross-venue arb match touches this slug;
* `smart_money_note` — a short honest one-liner derived from the G07 smart-money
  aggregate, or `null` when there is nothing to say.

**PUBLIC GET.** Reuses the H01 desk composition pieces (`_latest_edge`,
`_arb_match`, `build_smart_money_summary`) and the J02 alert-feed builder — but
kept deliberately compact. Cached with the desk-cache TTL pattern (`cached`
flag; keyed by slug). An unknown slug returns an honest **200**
`{found: false, slug, …nulls}` — never a 404, never fabricated data. Swept by
the I01 5xx guard (plain public GET with a `{slug}` path param).

**PATH NOTE:** the requested `/api/v1/markets/{slug}/snapshot` path is already
owned by the pre-existing FULL market snapshot (`MarketSnapshotResponse`, locked
shape + tests, 404 on unknown). To stay additive and never break that contract,
this compact share snapshot lives at `/markets/{slug}/share-snapshot`.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts_feed import _build_alert_feed, _family_of
from app.api.v1.desk import _arb_match, _latest_edge
from app.api.v1.smart_money import build_smart_money_summary
from app.core import snapshot_cache
from app.core.config import get_settings
from app.core.http_etag import etag_json_response
from app.db.session import get_db
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["market-snapshot"])
settings = get_settings()

SNAPSHOT_DISCLAIMER = (
    "Shareable research snapshot — model edge, top signal, arb and smart-money "
    "observations composed from existing analysis surfaces. Signal only; paper "
    "trading only — simulated funds, no execution."
)


def _edge_oneliner(
    edge: dict[str, Any] | None, book: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Compact ``{model_p, market_p, edge}`` from the desk edge + book, or None
    when there is no model prediction. ``market_p`` is the best reference YES
    price (asks, else bids); honest ``null`` when the book has no reference."""
    if edge is None:
        return None
    model_p = edge.get("predicted_prob")
    edge_vs_book = edge.get("edge_vs_book")
    yes_book = (book or {}).get("yes", {}) if book else {}
    levels = yes_book.get("asks") or yes_book.get("bids") or []
    market_p = round(float(levels[0]["price"]), 4) if levels else None
    return {
        "model_p": round(float(model_p), 4) if model_p is not None else None,
        "market_p": market_p,
        "edge": edge_vs_book,
    }


async def _top_signal(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    """Most-recent alert-family signal for the slug (family + H03 citation), or
    None. Reuses the J02 feed builder scoped to this one slug."""
    feed = await _build_alert_feed(
        db, effective_slugs=[slug], scope="explicit", since=None, limit=1
    )
    if not feed.items:
        return None
    item = feed.items[0]
    return {
        "family": _family_of(item.signal_type),
        "signal_type": item.signal_type,
        "created_at": item.created_at.isoformat(),
        "citation": item.citation.model_dump(),
    }


def _smart_money_note(summary: dict[str, Any]) -> str | None:
    """A short honest one-liner from the G07 aggregate, or None when there is no
    smart-money activity to report (never fabricated)."""
    holders = summary.get("top_holders", {})
    flows = summary.get("recent_large_flows", {})
    intensity = summary.get("trade_intensity", {})
    top_share = holders.get("top_share") or 0.0
    whale_count = flows.get("whale_count") or 0
    fill_count = intensity.get("fill_count") or 0
    if not top_share and not whale_count and not fill_count:
        return None
    parts: list[str] = []
    if top_share:
        parts.append(
            f"Top {holders.get('top_n', 0)} wallets hold "
            f"{round(top_share * 100)}% of open interest"
        )
    if whale_count:
        parts.append(f"{whale_count} recent large flow(s)")
    if fill_count:
        parts.append(f"{fill_count} paper fill(s) in window")
    return "; ".join(parts) + "."


async def build_share_snapshot_core(db: AsyncSession, slug: str) -> dict[str, Any]:
    """The compact per-market snapshot core reused by M02 and the O03 compare
    surface: ``{found, slug, title, yes_price, edge, top_signal, arb_matched,
    smart_money_note}``. An unknown slug returns an honest ``found: false`` with
    null fields — never fabricated data, never raises."""
    svc = MarketService(db)
    market_model = await svc.get_market_by_slug(slug)
    market = await svc.get_public_market_by_slug(slug)
    if market_model is None or market is None:
        return {
            "found": False,
            "slug": slug,
            "title": None,
            "yes_price": None,
            "edge": None,
            "top_signal": None,
            "arb_matched": False,
            "smart_money_note": None,
        }

    book = await OrderBookService(db).get_l2(market_model.id, depth=10)
    edge = await _latest_edge(db, slug, book)
    arb = await _arb_match(db, slug)
    smart_money = await build_smart_money_summary(db, slug)
    return {
        "found": True,
        "slug": slug,
        "title": market.title,
        "yes_price": market.yes_price,
        "edge": _edge_oneliner(edge, book),
        "top_signal": await _top_signal(db, slug),
        "arb_matched": arb is not None,
        "smart_money_note": _smart_money_note(smart_money),
    }


@router.get("/markets/{slug}/share-snapshot")
async def get_market_share_snapshot(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    if settings.desk_cache_enabled:
        cached_body = snapshot_cache.get(slug, settings.desk_cache_ttl_sec)
        if cached_body is not None:
            # M03: ETag over content (generated_at/cached excluded), so a cache
            # hit and a fresh build of the same content share one validator.
            return etag_json_response(request, {**cached_body, "cached": True})

    core = await build_share_snapshot_core(db, slug)
    response: dict[str, Any] = {
        **core,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": SNAPSHOT_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
        "cached": False,
    }
    if settings.desk_cache_enabled:
        snapshot_cache.put(slug, response)
    return etag_json_response(request, response)
