"""Master context composer (Loop V58 D3).

Builds a timestamped per-market JSON "master file" the prediction/pods layer
can read: whale pressure, venue gap, news signal, price trend, volume
percentile. Analysis only — every field carries capture timestamps for
leakage filtering.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Market, OddsSnapshot
from app.services.venue_gap_service import VenueGapService
from app.services.whale_flow_service import WhaleFlowService
from app.signals.venue_gap import bounded_venue_gap_feature


async def _price_trend(session: AsyncSession, slug: str) -> dict[str, Any]:
    """Simple 1h price delta from odds_snapshots (honest nulls when thin)."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=1)
    rows = (
        await session.execute(
            select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at >= cutoff,
            )
            .order_by(OddsSnapshot.captured_at.asc())
            .limit(200)
        )
    ).all()
    if not rows:
        latest = (
            await session.execute(
                select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
                .where(OddsSnapshot.market_slug == slug)
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()
        if latest is None:
            return {
                "implied_yes": None,
                "delta_1h": None,
                "points": 0,
                "as_of": None,
            }
        return {
            "implied_yes": float(latest[0]),
            "delta_1h": None,
            "points": 1,
            "as_of": latest[1].isoformat() if latest[1] else None,
        }
    first = float(rows[0][0])
    last = float(rows[-1][0])
    return {
        "implied_yes": last,
        "delta_1h": round(last - first, 6),
        "points": len(rows),
        "as_of": rows[-1][1].isoformat() if rows[-1][1] else None,
    }


async def _volume_percentile(session: AsyncSession, slug: str) -> dict[str, Any]:
    """Percentile of this market's volume among catalog peers (0-100)."""
    market = await session.scalar(select(Market).where(Market.slug == slug))
    if market is None:
        return {"volume": None, "percentile": None, "peer_count": 0}
    vol = int(market.volume or 0)
    total = int(
        await session.scalar(select(func.count()).select_from(Market)) or 0
    )
    if total <= 1:
        return {"volume": vol, "percentile": 50.0, "peer_count": total}
    below = int(
        await session.scalar(
            select(func.count()).select_from(Market).where(Market.volume < vol)
        )
        or 0
    )
    # Mid-rank percentile so ties don't claim 100% alone.
    percentile = round(100.0 * (below + 0.5) / total, 2)
    return {"volume": vol, "percentile": percentile, "peer_count": total}


async def _news_block(slug: str) -> dict[str, Any]:
    from app.signals.news_signal import get_cached_signal

    signal = get_cached_signal(slug)
    if signal is None:
        return {
            "available": False,
            "sentiment_score": None,
            "volume_score": None,
            "headline": None,
            "sources_count": 0,
            "captured_at": None,
        }
    return {
        "available": True,
        "sentiment_score": signal.sentiment_score,
        "volume_score": signal.volume_score,
        "headline": signal.headline,
        "sources_count": signal.sources_count,
        "polymarket_consensus": signal.polymarket_consensus,
        # Cache has no explicit capture time; surface generation time as as_of.
        "captured_at": datetime.now(UTC).isoformat(),
    }


async def build_market_context(
    session: AsyncSession,
    slug: str,
) -> dict[str, Any]:
    """Compose the master context document for one market slug."""
    settings = get_settings()
    now = datetime.now(UTC)

    market = await session.scalar(select(Market).where(Market.slug == slug))
    found = market is not None

    whale_svc = WhaleFlowService(session)
    pressure = await whale_svc.pressure_for(slug)
    whale_block = {
        "pressure": pressure.pressure,
        "event_count": pressure.event_count,
        "net_notional": pressure.net_notional,
        "total_notional": pressure.total_notional,
        "window_sec": pressure.window_sec,
        "captured_at": pressure.as_of.isoformat(),
    }

    gap_svc = VenueGapService(session)
    gap_row = await gap_svc.gap_for_slug(slug)
    if gap_row is None:
        venue_block: dict[str, Any] = {
            "available": False,
            "gap": None,
            "abs_gap": None,
            "bounded_feature": 0.0,
            "stale": None,
            "pm_slug": None,
            "ks_slug": None,
            "captured_at": None,
        }
    else:
        venue_block = {
            "available": True,
            "gap": float(gap_row.gap),
            "abs_gap": float(gap_row.abs_gap),
            "bounded_feature": bounded_venue_gap_feature(gap_row.gap),
            "pm_implied": float(gap_row.pm_implied),
            "ks_implied": float(gap_row.ks_implied),
            "stale": bool(gap_row.stale),
            "match_confidence": float(gap_row.match_confidence),
            "pm_slug": gap_row.pm_slug,
            "ks_slug": gap_row.ks_slug,
            "captured_at": gap_row.captured_at.isoformat()
            if gap_row.captured_at
            else None,
        }

    price = await _price_trend(session, slug)
    volume = await _volume_percentile(session, slug)
    news = await _news_block(slug)

    return {
        "found": found,
        "slug": slug,
        "title": market.title if market else None,
        "status": market.status.value if market and market.status else None,
        "whale": whale_block,
        "venue_gap": venue_block,
        "news": news,
        "price_trend": price,
        "volume": volume,
        # Flattened features for pods/prediction consumers
        "features": {
            "whale_pressure": whale_block["pressure"],
            "venue_gap": venue_block.get("gap"),
            "venue_gap_bounded": venue_block["bounded_feature"],
            "news_sentiment": news.get("sentiment_score"),
            "price_delta_1h": price.get("delta_1h"),
            "volume_percentile": volume.get("percentile"),
        },
        "generated_at": now.isoformat(),
        "signal_only": True,
        "paper_trading_only": settings.paper_trading_only,
        "disclaimer": (
            "Master market context — whale flow, cross-venue gap, news, "
            "price trend and volume percentile. All timestamps are capture "
            "times; consumers must filter to pre-close. Signal only."
        ),
    }


async def build_context_digest(
    session: AsyncSession,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    """Fleet digest: top whale pressures + top venue gaps + counts."""
    settings = get_settings()
    now = datetime.now(UTC)
    gap_svc = VenueGapService(session)
    top_gaps = await gap_svc.top_gaps(limit=limit, include_stale=True)

    # Aggregate recent whale activity by market (bounded).
    from app.db.models import WhaleEvent

    cutoff = now - timedelta(hours=1)
    whale_rows = (
        await session.execute(
            select(
                WhaleEvent.market_slug,
                func.count().label("n"),
                func.sum(WhaleEvent.notional).label("notional"),
            )
            .where(WhaleEvent.captured_at >= cutoff)
            .group_by(WhaleEvent.market_slug)
            .order_by(func.sum(WhaleEvent.notional).desc())
            .limit(limit)
        )
    ).all()

    whale_svc = WhaleFlowService(session)
    whale_top: list[dict[str, Any]] = []
    for slug, n, notional in whale_rows:
        p = await whale_svc.pressure_for(str(slug))
        whale_top.append(
            {
                "slug": str(slug),
                "pressure": p.pressure,
                "event_count": int(n),
                "notional_1h": float(notional or 0),
                "captured_at": p.as_of.isoformat(),
            }
        )

    return {
        "generated_at": now.isoformat(),
        "whale_top": whale_top,
        "venue_gaps_top": [
            {
                "pm_slug": g.pm_slug,
                "ks_slug": g.ks_slug,
                "gap": float(g.gap),
                "abs_gap": float(g.abs_gap),
                "stale": bool(g.stale),
                "captured_at": g.captured_at.isoformat() if g.captured_at else None,
            }
            for g in top_gaps
        ],
        "counts": {
            "whale_markets": len(whale_top),
            "venue_gaps": len(top_gaps),
        },
        "signal_only": True,
        "paper_trading_only": settings.paper_trading_only,
        "disclaimer": (
            "Fleet context digest — top whale flow and cross-venue gaps. "
            "Signal only; paper trading only."
        ),
    }
