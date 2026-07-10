"""O02 — Category intelligence aggregate (Loop V10).

``GET /api/v1/categories/{category}/summary`` — a PUBLIC GET per-category
aggregate composed READ-ONLY from existing surfaces:

* the local market catalog scoped to the category via the app's EXISTING
  category taxonomy (``MarketService._catalog_category_filter`` — the same
  filter Discover/markets use, e.g. ``sports``/``politics``/``crypto``/``nba``);
* the N01 opportunity rows (model-vs-market edge) for those markets, reusing the
  opportunities helpers — ``mean_abs_edge`` + up to 3 ``top_opportunities``;
* recent alert-family signal volume on those markets (the ``signal_events``
  store, keyed by slug);
* the O01 resolved-market review filtered to the category (``resolved_n`` +
  ``resolved_accuracy``).

**PUBLIC GET.** No new table, persists nothing, order path never imported. An
unknown/empty category degrades to an honest ``{found:false, ...zeros}`` (never
a 404, never fabricated). Cacheable (desk-cache TTL; additive ``cached`` flag).
Swept by the I01 5xx guard.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.opportunities import (
    _book_reference_price,
    _latest_model_probs,
    _top_signal,
)
from app.api.v1.resolved import resolved_review_rows, summarize_resolved
from app.core import opportunities_cache
from app.core.config import get_settings
from app.db.models import SignalEvent
from app.db.session import get_db
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["categories"])
settings = get_settings()

CATEGORIES_DISCLAIMER = (
    "Category intelligence — a read-only per-category aggregate of the model's "
    "edges, recent signals and resolved track record, composed from existing "
    "analysis surfaces. Signal only; paper trading only — simulated funds, no "
    "execution."
)

# A public GET must never do unbounded work: cap the markets scored per category.
_MAX_CANDIDATES = 200
# How far back a signal counts as "recent" for the category volume readout.
_RECENT_SIGNAL_WINDOW = timedelta(days=7)


async def _opportunity_rows_for_markets(
    db: AsyncSession, markets: list[Any]
) -> list[dict[str, Any]]:
    """N01 opportunity rows (same shape) for the given category markets.

    Only OPEN markets with BOTH a model probability and a market price yield a
    row (honest exclusions, never faked) — identical rules to the N01 scanner.
    """
    candidates = [
        m
        for m in markets
        if getattr(m.status, "value", str(m.status)).lower() == "open"
    ][:_MAX_CANDIDATES]
    slugs = [m.slug for m in candidates]
    model_probs = await _latest_model_probs(db, slugs)

    rows: list[dict[str, Any]] = []
    for m in candidates:
        model_p = model_probs.get(m.slug)
        if model_p is None:
            continue
        book = await OrderBookService(db).get_l2(m.id, depth=10)
        market_p = _book_reference_price(book)
        if market_p is None:
            market_p = m.yes_price
        if market_p is None:
            continue
        edge = round(abs(model_p - market_p), 4)
        rows.append(
            {
                "slug": m.slug,
                "title": m.title,
                "model_p": round(model_p, 4),
                "market_p": round(float(market_p), 4),
                "edge": edge,
                "direction": "YES" if model_p > market_p else "NO",
                "yes_price": m.yes_price,
                "liquidity": int(m.volume or 0),
            }
        )
    rows.sort(key=lambda r: (-r["edge"], -r["liquidity"], r["slug"]))
    return rows


async def _recent_signal_count(db: AsyncSession, slugs: list[str]) -> int:
    """Count of recent alert signals on the category's markets (signal_events is
    keyed by slug via ``market_id``). Zero when the category has no markets."""
    if not slugs:
        return 0
    since = datetime.now(UTC) - _RECENT_SIGNAL_WINDOW
    result = await db.execute(
        select(func.count())
        .select_from(SignalEvent)
        .where(SignalEvent.market_id.in_(slugs), SignalEvent.created_at >= since)
    )
    return int(result.scalar_one() or 0)


@router.get("/categories/{category}/summary")
async def get_category_summary(
    category: str = Path(..., description="Category slug (case-insensitive)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cat = (category or "").strip()
    cache_key = ("category-summary", cat.lower())
    if settings.desk_cache_enabled:
        cached_body = opportunities_cache.get(cache_key, settings.desk_cache_ttl_sec)
        if cached_body is not None:
            return {**cached_body, "cached": True}

    svc = MarketService(db)
    markets = await svc.list_public_markets(category=cat) if cat else []
    slugs = [m.slug for m in markets]

    opp_rows = await _opportunity_rows_for_markets(db, markets)
    edges = [r["edge"] for r in opp_rows]
    mean_abs_edge = round(sum(edges) / len(edges), 4) if edges else None

    # Perf (V12 Q02): top_signal is one query per market and is only ever
    # surfaced on the top 3 rows, so resolve it there instead of for every
    # scored candidate (was up to _MAX_CANDIDATES lookups, now ≤3).
    top_opportunities = opp_rows[:3]
    for row in top_opportunities:
        row["top_signal"] = await _top_signal(db, row["slug"])

    recent_signal_count = await _recent_signal_count(db, slugs)

    resolved_rows = await resolved_review_rows(db, category=cat) if cat else []
    resolved_summary = summarize_resolved(resolved_rows)

    market_count = len(markets)
    found = bool(cat) and (market_count > 0 or resolved_summary["n"] > 0)

    response: dict[str, Any] = {
        "category": cat,
        "found": found,
        "market_count": market_count,
        "mean_abs_edge": mean_abs_edge,
        "top_opportunities": top_opportunities,
        "recent_signal_count": recent_signal_count,
        "resolved_n": resolved_summary["n"],
        "resolved_accuracy": resolved_summary["accuracy"],
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": CATEGORIES_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
        "cached": False,
    }
    if settings.desk_cache_enabled:
        opportunities_cache.put(cache_key, response)
    return response
