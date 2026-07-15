from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import market_candles_cache
from app.core.market_candles_cache import MARKET_CANDLES_TTL_SEC
from app.data.candle_seed import (
    SeedCandle,
    bucket_snapshots,
    generate_candles,
    pad_candles,
)
from app.data.connectors.catalog_map import CATALOG_MAP
from app.db.models import OddsSnapshot
from app.db.session import get_db
from app.services.market_service import CATALOG_SLUGS, MarketService

router = APIRouter(prefix="/api/v1", tags=["markets"])

_LIVE_MIRROR_SOURCES = frozenset({"polymarket", "kalshi"})


def _is_live_mirror_source(source: str | None) -> bool:
    return source in _LIVE_MIRROR_SOURCES


def _is_accessible_mirror_market(slug: str, source: str | None) -> bool:
    return slug in CATALOG_SLUGS or _is_live_mirror_source(source)


@router.get("/markets/{slug}/candles")
async def get_market_candles(
    slug: str,
    points: int = Query(default=90, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
):
    """OHLCV candles with short per-(slug, points) TTL cache (Loop V43 P2).

    Public path only — cache keys are ``(slug, points)`` (the range dimension).
    Success-only puts; TTL <= 30s.
    """
    cache_key = ("market_candles", slug, int(points))
    cached = market_candles_cache.get(cache_key, MARKET_CANDLES_TTL_SEC)
    if cached is not None:
        return {**cached, "cached": True}

    body = await _build_market_candles(slug, points, db)
    # Success-only: put after full successful build.
    market_candles_cache.put(cache_key, {k: v for k, v in body.items() if k != "cached"})
    return body


async def _build_market_candles(
    slug: str, points: int, db: AsyncSession
) -> dict:
    market = await MarketService(db).get_market_by_slug(slug)
    if market is None or not _is_accessible_mirror_market(slug, market.source):
        raise HTTPException(status_code=404, detail="Market not found")

    is_live = _is_live_mirror_source(market.source)

    result = await db.execute(
        select(OddsSnapshot.captured_at, OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(points * 2)
    )
    # Fetch newest-first, then reverse so bucket_snapshots receives ascending order.
    rows = [
        (captured_at, float(implied))
        for captured_at, implied in reversed(result.all())
    ]

    entry = CATALOG_MAP.get(slug)
    end_price = entry.spec_price if entry is not None else 0.5

    if is_live:
        # Live mirrored markets never show synthetic candles — only real ticks.
        bucketed = bucket_snapshots(rows) if rows else []
        candles = bucketed
        source = "live"
    elif not rows:
        candles = generate_candles(slug, points, end_price, step_sec=3600)
        source = "seed"
    else:
        bucketed = bucket_snapshots(rows)
        candles = pad_candles(bucketed, slug, points, end_price, step_sec=3600)
        source = "db" if bucketed else "seed"

    return {
        "candles": [_candle_payload(candle) for candle in candles],
        "source": source,
        "cached": False,
    }


@router.get("/markets/{slug}/prices/latest")
async def get_latest_price(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    if slug not in CATALOG_SLUGS:
        market = await MarketService(db).get_market_by_slug(slug)
        if market is None or not _is_live_mirror_source(market.source):
            raise HTTPException(status_code=404, detail="Market not found")

    result = await db.execute(
        select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        entry = CATALOG_MAP.get(slug)
        yes = entry.spec_price if entry is not None else 0.5
        return {"slug": slug, "yes": yes, "no": round(1.0 - yes, 4), "ts": None, "source": "seed"}

    yes = float(row[0])
    return {
        "slug": slug,
        "yes": yes,
        "no": round(1.0 - yes, 4),
        "ts": row[1].isoformat(),
        "source": "db",
    }


@router.get("/markets/{slug}/history")
async def get_market_history(
    slug: str,
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Return daily [timestamp, yes_price] pairs for the past N days."""
    market = await MarketService(db).get_market_by_slug(slug)
    if market is None or not _is_accessible_mirror_market(slug, market.source):
        raise HTTPException(status_code=404, detail="Market not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(OddsSnapshot.captured_at, OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug)
        .where(OddsSnapshot.captured_at >= since)
        .order_by(OddsSnapshot.captured_at.asc())
    )
    rows = result.all()

    entry = CATALOG_MAP.get(slug)
    end_price = entry.spec_price if entry is not None else 0.5

    if not rows and _is_live_mirror_source(market.source):
        return {"history": [], "source": "live"}

    if not rows:
        now = datetime.now(timezone.utc)
        history = []
        for i in range(days):
            ts = now - timedelta(days=days - 1 - i)
            frac = i / max(days - 1, 1)
            price = round(0.5 + frac * (end_price - 0.5), 4)
            history.append({"timestamp": int(ts.timestamp()), "yes_price": price})
        return {"history": history, "source": "synthetic"}

    history = [
        {"timestamp": int(captured_at.timestamp()), "yes_price": float(implied_yes)}
        for captured_at, implied_yes in rows
    ]
    return {"history": history, "source": "db"}


def _candle_payload(candle: SeedCandle) -> dict[str, float | int]:
    return {
        "time": candle.time,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
    }
