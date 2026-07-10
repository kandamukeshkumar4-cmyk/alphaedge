"""N02 — Forecast drivers (Loop V9).

``GET /api/v1/markets/{slug}/drivers`` — the top drivers behind the current model
probability for ONE market, so the market page can answer "why does the model
think this?". Composed READ-ONLY from existing stores:

* the **model-vs-market gap** — the latest ``PredictionLog`` model P(YES) vs the
  market-implied price (the SAME edge source ``/api/v1/desk`` (H01) and the M02
  share snapshot use);
* recent **alert-family signals** on the slug (from the signal store), each with
  its family + H03 citation — the ``news:mispricing`` signals carry the news
  headline/url, i.e. the news catalysts behind the forecast.

Each driver is ``{label, direction, note, family, citation}`` where ``direction``
is ``"favors YES"`` / ``"favors NO"`` / ``"neutral"``. ``family`` + ``citation``
are honest ``null`` for the non-signal gap driver.

**PUBLIC GET.** No new pipeline, no new table, persists nothing, order path never
imported, no network (the live news fetcher is NOT called — news catalysts come
from persisted signal citations). An unknown slug returns an honest **200**
``{found: false, …}`` (never a 404); a known market with no model and no signals
returns ``{found: true, drivers: []}``. No fabricated data. Swept by the I01 5xx
guard (plain public GET with a ``{slug}`` path param).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts_feed import _build_alert_feed, _family_of
from app.api.v1.desk import _latest_edge
from app.core.config import get_settings
from app.db.session import get_db
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["market-drivers"])
settings = get_settings()

DRIVERS_DISCLAIMER = (
    "Forecast drivers — the model-vs-market gap and the recent signals behind "
    "the current model probability, composed from existing analysis surfaces. "
    "Signal only; paper trading only — simulated funds, no execution."
)

# Anchor epsilon: within this gap the lean is reported as neutral (consistent
# with the forecast-scoring anchor epsilon used elsewhere).
_NEUTRAL_EPS = 0.02


def _lean(model_p: float | None, market_p: float | None) -> str:
    """Direction the evidence leans, honest neutral inside the anchor epsilon."""
    if model_p is None or market_p is None:
        return "neutral"
    diff = model_p - market_p
    if abs(diff) < _NEUTRAL_EPS:
        return "neutral"
    return "favors YES" if diff > 0 else "favors NO"


def _book_reference_price(book: dict[str, Any] | None) -> float | None:
    yes_book = (book or {}).get("yes", {}) if book else {}
    levels = yes_book.get("asks") or yes_book.get("bids") or []
    if not levels:
        return None
    return round(float(levels[0]["price"]), 4)


async def _signal_drivers(
    db: AsyncSession, slug: str, limit: int
) -> list[dict[str, Any]]:
    """Recent alert-family signals on the slug as drivers (family + citation).
    Reuses the J02 feed builder — the same source the feed/desk use."""
    feed = await _build_alert_feed(
        db, effective_slugs=[slug], scope="explicit", since=None, limit=limit
    )
    drivers: list[dict[str, Any]] = []
    for item in feed.items:
        citation = item.citation.model_dump()
        family = _family_of(item.signal_type)
        headline = citation.get("headline")
        label = headline if headline else (family or item.signal_type)
        drivers.append(
            {
                "label": label,
                "direction": _lean(citation.get("model_p"), citation.get("market_p")),
                "note": f"{family or item.signal_type} signal",
                "family": family,
                "citation": citation,
            }
        )
    return drivers


@router.get("/markets/{slug}/drivers")
async def get_market_drivers(
    slug: str,
    signals_limit: int = Query(default=5, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = MarketService(db)
    market_model = await svc.get_market_by_slug(slug)
    market = await svc.get_public_market_by_slug(slug)
    found = market_model is not None and market is not None

    base = {
        "slug": slug,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": DRIVERS_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    if not found:
        # Honest 200 for an unknown slug — never a 404, never fabricated data.
        return {
            "found": False,
            "model_p": None,
            "market_p": None,
            "gap": None,
            "drivers": [],
            **base,
        }

    book = await OrderBookService(db).get_l2(market_model.id, depth=10)
    edge = await _latest_edge(db, slug, book)
    model_p = edge["predicted_prob"] if edge else None
    market_p = _book_reference_price(book)
    if market_p is None:
        market_p = market.yes_price
    gap = (
        round(model_p - market_p, 4)
        if model_p is not None and market_p is not None
        else None
    )

    drivers: list[dict[str, Any]] = []
    # The model-vs-market gap driver (only when both numbers exist — never faked).
    if gap is not None:
        drivers.append(
            {
                "label": "Model vs market gap",
                "direction": _lean(model_p, market_p),
                "note": (
                    f"Model {round(model_p, 4)} vs market {round(float(market_p), 4)} "
                    f"({gap:+.4f})."
                ),
                "family": None,
                "citation": None,
            }
        )
    drivers.extend(await _signal_drivers(db, slug, signals_limit))

    return {
        "found": True,
        "model_p": round(model_p, 4) if model_p is not None else None,
        "market_p": round(float(market_p), 4) if market_p is not None else None,
        "gap": gap,
        "drivers": drivers,
        **base,
    }
