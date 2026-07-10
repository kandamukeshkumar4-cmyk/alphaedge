"""O01 — Resolved-market review (Loop V10).

``GET /api/v1/resolved?limit=&offset=`` — a browsable, PUBLIC GET list of
RESOLVED external markets with the model's prediction vs the actual outcome, so
anyone can inspect how the model actually did on real resolutions (the public
track record that research says is undersupplied while distrust peaks).

Each row: ``{slug, title, resolved_at, outcome, model_p_at_close, correct,
brier}`` plus a summary header ``{n, accuracy, mean_brier, thin_data}``.

Source: the SAME resolved-forecast source as ``/api/v1/track-record`` and
``/api/v1/backtest/summary`` — scored LIVE forecasts on RESOLVED external
markets (``ForecastLog`` x ``ForecastScore`` x ``ExternalMarket``). NO invented
outcomes; only real resolutions. ``ExternalMarket`` has no dedicated slug column
so ``external_id`` is the stable per-market key (same convention as the K01
self-serve backtest). One row PER resolved market: the model probability at
close is the LATEST LIVE forecast (max ``seq``/``locked_at``) before resolution.

**PUBLIC GET.** Read-only composition of existing stores — no new table,
persists nothing, order write path never imported. Bounded pagination.
Cacheable (desk-cache TTL pattern; additive ``cached`` flag) + weak-ETag. Honest
empty ``{rows: [], summary: {n: 0, ...}}``. Swept by the I01 5xx guard.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import opportunities_cache
from app.core.config import get_settings
from app.core.http_etag import etag_json_response
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
)
from app.db.session import get_db
from app.forecasting import BRIER_MIN_SAMPLE

router = APIRouter(prefix="/api/v1", tags=["resolved"])
settings = get_settings()

# Same thin-data threshold as the track-record surface (BRIER_MIN_SAMPLE) so the
# two never disagree on when the record is "small sample".
THIN_DATA_THRESHOLD = BRIER_MIN_SAMPLE

RESOLVED_DISCLAIMER = (
    "Resolved-market review — the model's prediction vs the REAL outcome on "
    "resolved external markets (same resolved source as the track record). No "
    "invented outcomes; only real resolutions. Signal only; paper trading only "
    "— simulated funds, no execution."
)


async def resolved_review_rows(
    db: AsyncSession, *, category: str | None = None
) -> list[dict[str, Any]]:
    """One review row PER resolved external market, newest resolution first.

    The model probability at close is the LATEST LIVE forecast on the market
    (max ``seq`` then ``locked_at``). Optionally scoped to ``ExternalMarket.
    category`` (case-insensitive) for the O02 category aggregate. Non-finite
    probabilities (Postgres NUMERIC 'NaN') are dropped so the Brier math never
    raises a 500.
    """
    stmt = (
        select(
            ForecastLog.external_market_id,
            ExternalMarket.external_id,
            ExternalMarket.title,
            ExternalMarket.resolved_at,
            ForecastScore.actual_outcome,
            ForecastLog.user_probability,
            ForecastLog.seq,
            ForecastLog.locked_at,
        )
        .join(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
        .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
        .where(
            ForecastLog.mode == ForecastMode.LIVE,
            ExternalMarket.status == ExternalMarketStatus.RESOLVED,
        )
    )
    if category is not None:
        # ExternalMarket carries its own freeform category string; match it
        # case-insensitively (the resolved taxonomy is independent of the local
        # catalog filter, so this is a best-effort honest scope).
        stmt = stmt.where(
            ExternalMarket.category.isnot(None),
            func.lower(ExternalMarket.category) == category.strip().lower(),
        )

    rows = (await db.execute(stmt)).all()

    # Keep the LATEST LIVE forecast per market as the close prediction.
    best: dict[Any, dict[str, Any]] = {}
    for (
        market_id,
        external_id,
        title,
        resolved_at,
        actual_outcome,
        user_probability,
        seq,
        locked_at,
    ) in rows:
        if user_probability is None or actual_outcome is None:
            continue
        p = float(user_probability)
        if not math.isfinite(p):
            continue
        rank = (seq if seq is not None else -1, locked_at or datetime.min)
        existing = best.get(market_id)
        if existing is not None and existing["_rank"] >= rank:
            continue
        outcome_int = int(actual_outcome)
        best[market_id] = {
            "_rank": rank,
            "slug": external_id,
            "title": title,
            "resolved_at": resolved_at,
            "outcome": "YES" if outcome_int == 1 else "NO",
            "model_p_at_close": round(p, 4),
            "correct": (p >= 0.5) == (outcome_int == 1),
            "brier": round((p - outcome_int) ** 2, 6),
        }

    result = [{k: v for k, v in row.items() if k != "_rank"} for row in best.values()]
    # Newest resolution first (None last), then slug for a stable deterministic
    # order under pagination.
    result.sort(
        key=lambda r: (
            r["resolved_at"] is None,
            r["resolved_at"] and -r["resolved_at"].timestamp() or 0.0,
            r["slug"] or "",
        )
    )
    return result


def summarize_resolved(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """``{n, accuracy, mean_brier, thin_data}`` over ALL supplied review rows."""
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "accuracy": None,
            "mean_brier": None,
            "thin_data": True,
            "thin_data_threshold": THIN_DATA_THRESHOLD,
        }
    accuracy = sum(1 for r in rows if r["correct"]) / n
    mean_brier = sum(r["brier"] for r in rows) / n
    return {
        "n": n,
        "accuracy": round(accuracy, 4),
        "mean_brier": round(mean_brier, 6),
        "thin_data": n < THIN_DATA_THRESHOLD,
        "thin_data_threshold": THIN_DATA_THRESHOLD,
    }


@router.get("/resolved")
async def get_resolved_review(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Response:
    cache_key = ("resolved", limit, offset)
    if settings.desk_cache_enabled:
        cached_body = opportunities_cache.get(cache_key, settings.desk_cache_ttl_sec)
        if cached_body is not None:
            return etag_json_response(request, {**cached_body, "cached": True})

    all_rows = await resolved_review_rows(db)
    summary = summarize_resolved(all_rows)
    page = all_rows[offset : offset + limit]
    # Serialize datetimes for the JSON body (etag helper also encodes, but keep
    # the cached body plain-JSON-friendly and identical on a cache hit).
    rows_out = [
        {
            **row,
            "resolved_at": (
                row["resolved_at"].isoformat() if row["resolved_at"] else None
            ),
        }
        for row in page
    ]

    response: dict[str, Any] = {
        "rows": rows_out,
        "summary": summary,
        "count": len(rows_out),
        "limit": limit,
        "offset": offset,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": RESOLVED_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
        "cached": False,
    }
    if settings.desk_cache_enabled:
        opportunities_cache.put(cache_key, response)
    return etag_json_response(request, response)
