"""N01 — Opportunity scanner (Loop V9).

``GET /api/v1/opportunities?limit=&min_liquidity=&direction=`` — a ranked,
READ-ONLY VIEW of the markets where the model most disagrees with the market,
so a trader can find the biggest edges right now in ONE call. Each row:

* ``model_p`` — the model's P(YES): the latest ``PredictionLog.predicted_prob``
  for the slug (the SAME edge source ``/api/v1/desk`` (H01) and the M02 share
  snapshot use). A market with NO model prediction is EXCLUDED honestly — never
  faked.
* ``market_p`` — the market-implied P(YES): the best reference YES price from
  the local order book (asks, else bids — same math as desk/M02), falling back
  to the latest odds-snapshot ``yes_price`` when there is no book. A market with
  neither is EXCLUDED (no market price → no edge to rank).
* ``edge`` — the absolute model-vs-market gap ``|model_p − market_p|`` (the rank
  key; highest first).
* ``direction`` — ``"YES"`` when ``model_p > market_p`` else ``"NO"`` (which side
  the model leans; the sign of the gap).
* ``yes_price`` — the market row's displayed YES price (odds snapshot), honest
  ``null`` when there is no snapshot.
* ``liquidity`` — the market ``volume`` (the liquidity proxy the catalog already
  ranks by); the ``min_liquidity`` floor filters on it.
* ``top_signal`` — the most recent alert-family signal on the slug
  (``{family, citation}`` reusing the J02 feed builder + H03 citation), or
  ``null``.

**PUBLIC GET.** Composition of EXISTING services only — no new pipeline, no new
table, persists nothing, order write path never imported. This is a ranked view,
NEVER an order feed. Cacheable (desk-cache TTL pattern; additive ``cached``
flag). Swept by the I01 5xx guard.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts_feed import _build_alert_feed, _family_of
from app.core import opportunities_cache
from app.core.config import get_settings
from app.core.http_etag import etag_json_response
from app.db.models import PredictionLog
from app.db.session import get_db
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["opportunities"])
settings = get_settings()

OPPORTUNITIES_DISCLAIMER = (
    "Opportunity scanner — a ranked, read-only view of the markets where the "
    "model most disagrees with the market, composed from existing forecast and "
    "market data. Signal only; paper trading only — simulated funds, no "
    "execution. This is NOT an order feed."
)

# A public GET must never do unbounded work: cap the candidate markets we score.
_MAX_CANDIDATES = 200


async def _latest_model_probs(
    db: AsyncSession, slugs: list[str]
) -> dict[str, float]:
    """Latest ``predicted_prob`` per slug in ONE query (the desk/M02 edge source).

    Ordered by slug then ``predicted_at`` desc so the first row seen per slug is
    the newest. Slugs with no prediction are simply absent (→ excluded upstream).
    """
    if not slugs:
        return {}
    rows = (
        await db.execute(
            select(
                PredictionLog.market_slug,
                PredictionLog.predicted_prob,
            )
            .where(PredictionLog.market_slug.in_(slugs))
            .order_by(
                PredictionLog.market_slug,
                PredictionLog.predicted_at.desc(),
            )
        )
    ).all()
    latest: dict[str, float] = {}
    for slug, prob in rows:
        if slug not in latest:
            latest[slug] = float(prob)
    return latest


def _book_reference_price(book: dict[str, Any] | None) -> float | None:
    """Best reference YES price (asks, else bids) — same math as desk/M02."""
    yes_book = (book or {}).get("yes", {}) if book else {}
    levels = yes_book.get("asks") or yes_book.get("bids") or []
    if not levels:
        return None
    return round(float(levels[0]["price"]), 4)


async def _top_signal(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    """Most-recent alert-family signal for the slug (family + H03 citation), or
    ``None``. Reuses the J02 feed builder scoped to this one slug."""
    feed = await _build_alert_feed(
        db, effective_slugs=[slug], scope="explicit", since=None, limit=1
    )
    if not feed.items:
        return None
    item = feed.items[0]
    return {
        "family": _family_of(item.signal_type),
        "citation": item.citation.model_dump(),
    }


@router.get("/opportunities")
async def get_opportunities(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    min_liquidity: int = Query(default=0, ge=0),
    direction: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # Normalize the optional direction filter (honest 200 on a bad value → no
    # filter, never a 422 that would break the public-GET contract).
    dir_filter: str | None = None
    if direction is not None:
        d = direction.strip().upper()
        if d in ("YES", "NO"):
            dir_filter = d

    cache_key = ("opportunities", limit, min_liquidity, dir_filter or "")
    if settings.desk_cache_enabled:
        cached_body = opportunities_cache.get(cache_key, settings.desk_cache_ttl_sec)
        if cached_body is not None:
            return etag_json_response(request, {**cached_body, "cached": True})

    svc = MarketService(db)
    markets, _ = await svc.list_public_markets(sort="volume")
    # Only score live markets (resolved markets have a known outcome — no edge),
    # and never do unbounded work.
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
            continue  # honest exclusion — no model probability, never faked
        liquidity = int(m.volume or 0)
        if liquidity < min_liquidity:
            continue
        book = await OrderBookService(db).get_l2(m.id, depth=10)
        market_p = _book_reference_price(book)
        if market_p is None:
            market_p = m.yes_price  # fall back to the odds-snapshot yes_price
        if market_p is None:
            continue  # no market price → no edge to rank; honest exclusion
        edge = round(abs(model_p - market_p), 4)
        row_direction = "YES" if model_p > market_p else "NO"
        if dir_filter is not None and row_direction != dir_filter:
            continue
        rows.append(
            {
                "slug": m.slug,
                "title": m.title,
                "model_p": round(model_p, 4),
                "market_p": round(float(market_p), 4),
                "edge": edge,
                "direction": row_direction,
                "yes_price": m.yes_price,
                "liquidity": liquidity,
            }
        )

    # Rank: biggest absolute edge first, then deeper liquidity, then slug for a
    # stable deterministic order.
    rows.sort(key=lambda r: (-r["edge"], -r["liquidity"], r["slug"]))
    rows = rows[:limit]

    # Perf (V12 Q02): the top_signal lookup is one query per market and does NOT
    # affect ranking, so resolve it ONLY for the ≤limit rows we actually return
    # instead of every scored candidate (was up to _MAX_CANDIDATES lookups).
    for row in rows:
        row["top_signal"] = await _top_signal(db, row["slug"])

    response: dict[str, Any] = {
        "opportunities": rows,
        "count": len(rows),
        "limit": limit,
        "min_liquidity": min_liquidity,
        "direction": dir_filter,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": OPPORTUNITIES_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
        "cached": False,
    }
    if settings.desk_cache_enabled:
        opportunities_cache.put(cache_key, response)
    return etag_json_response(request, response)
