"""Point-in-time persistence for alpha validation inputs.

Lock-time values and their availability reasons are stored separately from the
append-only forecast log. Historical recovery is deliberately conservative:
an absent value stays absent unless the original lock-time value is provable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import math
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.factors import FACTOR_FUNCTIONS
from app.db.models import (
    AlphaFactorSnapshot,
    AlphaClosingLine,
    AnalystBrief,
    ExternalMarket,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Market,
    MarketSentimentSnapshot,
    OddsSnapshot,
    Platform,
    VenueGap,
)
from app.services.whale_flow_service import WhaleFlowService


CAPTURE_VERSION = "v1"
PRICE_WINDOW = timedelta(hours=1)
PRICE_SAMPLE_LIMIT = 200
DEBATE_LENSES = frozenset({"news-bull", "news-bear", "base-rate-skeptic"})
CLOSING_SOURCE = "odds_snapshot_last_pre_close_v1"
CLOSING_POLICY_VERSION = "last_pre_close_v1"


async def capture_factor_snapshot(
    session: AsyncSession,
    forecast: ForecastLog,
    external_market: ExternalMarket,
    *,
    backfilled: bool = False,
) -> AlphaFactorSnapshot:
    """Persist the factor inputs knowable at this forecast's lock timestamp."""
    existing = await session.scalar(
        select(AlphaFactorSnapshot).where(
            AlphaFactorSnapshot.forecast_id == forecast.id
        )
    )
    if existing is not None:
        return existing

    observed_at = _utc(forecast.locked_at)
    model_probability = _probability(forecast.user_probability)
    market_probability = _probability(forecast.market_implied_probability)
    edge = (
        None
        if model_probability is None or market_probability is None
        else model_probability - market_probability
    )
    seconds = forecast.time_to_resolution_seconds
    hours_to_lock = None if seconds is None else float(seconds) / 3600.0
    features = {
        "model_probability": model_probability,
        "market_implied_probability": market_probability,
        "edge": edge,
        "hours_to_lock": hours_to_lock,
    }
    provenance: dict[str, dict[str, Any]] = {
        "model_edge": _availability(
            model_probability is not None and market_probability is not None,
            fields=("model_probability", "market_implied_probability"),
            source="forecast_log_columns",
            backfilled=backfilled,
        ),
        "time_decay": _availability(
            hours_to_lock is not None and hours_to_lock >= 0 and edge is not None,
            fields=("hours_to_lock", "edge"),
            source="forecast_log_columns",
            backfilled=backfilled,
        ),
    }
    if backfilled:
        provenance.update(_historically_unavailable())
        provenance["regime_context"] = {
            "available": False,
            "reason": "historical_volume_not_reconstructible",
            "backfilled": True,
        }
    else:
        slugs = _source_slugs(external_market)
        volume, volume_provenance = await _regime_volume(
            session,
            external_market,
            observed_at,
        )
        if volume is not None:
            features["volume"] = volume
        category = (
            external_market.category.strip()
            if isinstance(external_market.category, str)
            and external_market.category.strip()
            else None
        )
        if category is not None:
            features["category"] = category
        if (
            volume_provenance.get("available")
            and hours_to_lock is not None
            and hours_to_lock >= 0.0
            and category is not None
        ):
            volume_provenance.update(
                {
                    "fields": ["volume", "hours_to_lock", "category"],
                    "category_source": "external_markets",
                }
            )
        elif volume_provenance.get("available"):
            volume_provenance = {
                "available": False,
                "reason": "missing_lock_time_regime_context",
                "backfilled": False,
            }
        provenance["regime_context"] = volume_provenance

        price_history, price_provenance = await _price_history(
            session, slugs, observed_at
        )
        if price_history is not None:
            features["price_history"] = price_history
        provenance["momentum"] = price_provenance
        provenance["mean_reversion"] = dict(price_provenance)

        whale_value, whale_provenance = await _whale_flow(
            session, slugs, observed_at
        )
        if whale_value is not None:
            features["whale_flow"] = whale_value
        provenance["whale_flow"] = whale_provenance

        news_values, news_provenance = await _news_sentiment(
            session, slugs, observed_at
        )
        features.update(news_values)
        provenance["news_sentiment"] = news_provenance

        venue_values, venue_provenance = await _cross_venue(
            session, slugs, observed_at
        )
        features.update(venue_values)
        provenance["cross_venue"] = venue_provenance
    factor_values = _capture_factor_values(features, provenance)
    snapshot = AlphaFactorSnapshot(
        forecast_id=forecast.id,
        external_market_id=external_market.id,
        observed_at=observed_at,
        features=features,
        factor_values=factor_values,
        factor_provenance=provenance,
        capture_version=CAPTURE_VERSION,
        backfilled=backfilled,
    )
    try:
        async with session.begin_nested():
            session.add(snapshot)
            await session.flush()
        return snapshot
    except IntegrityError:
        concurrent = await session.scalar(
            select(AlphaFactorSnapshot).where(
                AlphaFactorSnapshot.forecast_id == forecast.id
            )
        )
        if concurrent is None:
            raise
        return concurrent


async def capture_closing_lines(
    session: AsyncSession,
    external_market: ExternalMarket,
    *,
    forecasts: list[ForecastLog] | None = None,
    backfilled: bool = False,
) -> int:
    """Persist the last observed pre-close market line for eligible forecasts.

    This is an explicit estimate policy over ``odds_snapshots``, not recovery
    of a previously written closing value. A missing snapshot stays missing.
    """
    cutoff_at = external_market.close_at
    if cutoff_at is None:
        return 0
    cutoff_at = _utc(cutoff_at)
    if forecasts is None:
        forecasts = list(
            (
                await session.scalars(
                    select(ForecastLog).where(
                        ForecastLog.external_market_id == external_market.id
                    )
                )
            ).all()
        )
    if not forecasts:
        return 0

    existing_ids = set(
        (
            await session.scalars(
                select(AlphaClosingLine.forecast_id).where(
                    AlphaClosingLine.forecast_id.in_(
                        [forecast.id for forecast in forecasts]
                    )
                )
            )
        ).all()
    )
    odds = (
        await session.execute(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.market_slug.in_(_source_slugs(external_market)),
                OddsSnapshot.captured_at <= cutoff_at,
            )
            .order_by(OddsSnapshot.captured_at.desc(), OddsSnapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if odds is None:
        return 0
    observed_at = _utc(odds.captured_at)
    probability = _probability(odds.implied_yes)
    if probability is None:
        return 0

    created = 0
    for forecast in forecasts:
        if forecast.id in existing_ids or _utc(forecast.locked_at) >= observed_at:
            continue
        line = AlphaClosingLine(
            forecast_id=forecast.id,
            external_market_id=external_market.id,
            source_snapshot_id=odds.id,
            closing_implied_probability=Decimal(str(probability)),
            observed_at=observed_at,
            cutoff_at=cutoff_at,
            source=CLOSING_SOURCE,
            policy_version=CLOSING_POLICY_VERSION,
            is_estimate=True,
            backfilled=backfilled,
        )
        try:
            async with session.begin_nested():
                session.add(line)
                await session.flush()
            created += 1
        except IntegrityError:
            concurrent = await session.scalar(
                select(AlphaClosingLine.id).where(
                    AlphaClosingLine.forecast_id == forecast.id
                )
            )
            if concurrent is None:
                raise
    return created


async def backfill_alpha_validation_history(
    session: AsyncSession,
    *,
    limit: int = 1000,
) -> dict[str, int]:
    """Recover only historical values provable from persisted source rows."""
    bounded_limit = min(max(int(limit), 1), 5000)
    factor_snapshots = closing_lines = closing_line_gaps = scanned = 0
    last_locked_at: datetime | None = None
    last_forecast_id: UUID | None = None
    while True:
        query = (
            select(
                ForecastLog,
                ExternalMarket,
                AlphaFactorSnapshot.id.label("factor_snapshot_id"),
                AlphaClosingLine.id.label("closing_line_id"),
            )
            .join(
                ExternalMarket,
                ExternalMarket.id == ForecastLog.external_market_id,
            )
            .join(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
            .outerjoin(
                AlphaFactorSnapshot,
                AlphaFactorSnapshot.forecast_id == ForecastLog.id,
            )
            .outerjoin(
                AlphaClosingLine,
                AlphaClosingLine.forecast_id == ForecastLog.id,
            )
            .where(
                ForecastLog.mode == ForecastMode.LIVE,
                or_(
                    AlphaFactorSnapshot.id.is_(None),
                    AlphaClosingLine.id.is_(None),
                ),
            )
            .order_by(ForecastLog.locked_at.asc(), ForecastLog.id.asc())
            .limit(bounded_limit)
        )
        if last_locked_at is not None:
            assert last_forecast_id is not None
            query = query.where(
                or_(
                    ForecastLog.locked_at > last_locked_at,
                    and_(
                        ForecastLog.locked_at == last_locked_at,
                        ForecastLog.id > last_forecast_id,
                    ),
                )
            )
        rows = (await session.execute(query)).all()
        if not rows:
            break
        scanned += len(rows)
        for row in rows:
            forecast = row.ForecastLog
            market = row.ExternalMarket
            if row.factor_snapshot_id is None:
                await capture_factor_snapshot(
                    session,
                    forecast,
                    market,
                    backfilled=True,
                )
                factor_snapshots += 1
            if row.closing_line_id is None:
                created = await capture_closing_lines(
                    session,
                    market,
                    forecasts=[forecast],
                    backfilled=True,
                )
                closing_lines += created
                if created == 0:
                    closing_line_gaps += 1
        last_locked_at = rows[-1].ForecastLog.locked_at
        last_forecast_id = rows[-1].ForecastLog.id
    return {
        "scanned": scanned,
        "factor_snapshots": factor_snapshots,
        "closing_lines": closing_lines,
        "closing_line_gaps": closing_line_gaps,
    }


def _historically_unavailable() -> dict[str, dict[str, Any]]:
    return {
        factor: {
            "available": False,
            "reason": "historical_value_not_reconstructible",
            "backfilled": True,
        }
        for factor in (
            "whale_flow",
            "momentum",
            "mean_reversion",
            "news_sentiment",
            "cross_venue",
        )
    }


def _capture_factor_values(
    features: dict[str, Any],
    provenance: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Freeze scores so later factor-code changes cannot rewrite history."""
    values: dict[str, float] = {}
    for name, function in FACTOR_FUNCTIONS.items():
        capture = provenance.get(name)
        if not isinstance(capture, dict) or not capture.get("available"):
            continue
        result = function(features)
        score = result.get("score")
        available = result.get("provenance", {}).get("available")
        if (
            not available
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            provenance[name] = {
                **capture,
                "available": False,
                "reason": "factor_value_unavailable_at_capture",
            }
            continue
        values[name] = float(score)
    return values


async def _regime_volume(
    session: AsyncSession,
    external_market: ExternalMarket,
    observed_at: datetime,
) -> tuple[float | None, dict[str, Any]]:
    venue_source = {
        Platform.POLYMARKET: "polymarket",
        Platform.KALSHI: "kalshi",
    }.get(external_market.platform)
    if venue_source is None:
        return None, {
            "available": False,
            "reason": "unsupported_regime_volume_source",
            "backfilled": False,
        }
    row = (
        await session.execute(
            select(
                Market.volume,
                Market.slug,
                Market.source,
                Market.last_synced_at,
            )
            .where(
                Market.source == venue_source,
                func.lower(Market.external_slug)
                == external_market.external_id.strip().lower(),
                Market.last_synced_at.is_not(None),
                Market.last_synced_at <= observed_at,
            )
            .order_by(Market.last_synced_at.desc(), Market.id.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None, {
            "available": False,
            "reason": "missing_prelock_volume_snapshot",
            "backfilled": False,
        }
    volume = _number(row.volume)
    if volume is None or volume < 0.0:
        return None, {
            "available": False,
            "reason": "invalid_prelock_volume_snapshot",
            "backfilled": False,
        }
    return volume, {
        "available": True,
        "fields": ["volume"],
        "source": "markets",
        "venue_source": row.source,
        "market_slug": row.slug,
        "observed_at": _utc(row.last_synced_at).isoformat(),
        "backfilled": False,
    }


async def _price_history(
    session: AsyncSession,
    slugs: list[str],
    observed_at: datetime,
) -> tuple[list[float] | None, dict[str, Any]]:
    cutoff = observed_at - PRICE_WINDOW
    for slug in slugs:
        rows = (
            await session.execute(
                select(
                    OddsSnapshot.implied_yes,
                    OddsSnapshot.captured_at,
                    OddsSnapshot.source,
                )
                .where(
                    OddsSnapshot.market_slug == slug,
                    OddsSnapshot.captured_at >= cutoff,
                    OddsSnapshot.captured_at <= observed_at,
                )
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(PRICE_SAMPLE_LIMIT)
            )
        ).all()
        if len(rows) < 2:
            continue
        rows.reverse()
        return (
            [float(row.implied_yes) for row in rows],
            {
                "available": True,
                "fields": ["price_history"],
                "source": "odds_snapshots",
                "market_slug": slug,
                "window_sec": int(PRICE_WINDOW.total_seconds()),
                "sample_count": len(rows),
                "first_observed_at": _utc(rows[0].captured_at).isoformat(),
                "last_observed_at": _utc(rows[-1].captured_at).isoformat(),
                "source_names": sorted({str(row.source) for row in rows}),
                "backfilled": False,
            },
        )
    return None, {
        "available": False,
        "reason": "insufficient_prelock_price_history",
        "backfilled": False,
    }


async def _whale_flow(
    session: AsyncSession,
    slugs: list[str],
    observed_at: datetime,
) -> tuple[float | None, dict[str, Any]]:
    service = WhaleFlowService(session)
    for slug in slugs:
        pressure = await service.pressure_for(slug, as_of=observed_at)
        if pressure.event_count <= 0:
            continue
        return (
            float(pressure.pressure),
            {
                "available": True,
                "fields": ["whale_flow"],
                "source": "whale_events",
                "market_slug": slug,
                "window_sec": float(pressure.window_sec),
                "event_count": int(pressure.event_count),
                "observed_at": _utc(pressure.as_of).isoformat(),
                "backfilled": False,
            },
        )
    return None, {
        "available": False,
        "reason": "no_prelock_whale_events",
        "backfilled": False,
    }


async def _news_sentiment(
    session: AsyncSession,
    slugs: list[str],
    observed_at: datetime,
) -> tuple[dict[str, float], dict[str, Any]]:
    for slug in slugs:
        news = (
            await session.execute(
                select(
                    MarketSentimentSnapshot.sentiment_score,
                    MarketSentimentSnapshot.captured_at,
                    MarketSentimentSnapshot.source,
                )
                .where(
                    MarketSentimentSnapshot.market_slug == slug,
                    MarketSentimentSnapshot.captured_at <= observed_at,
                )
                .order_by(MarketSentimentSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()
        if news is None:
            continue
        debate_rows = (
            await session.execute(
                select(AnalystBrief)
                .where(
                    AnalystBrief.market_slug == slug,
                    AnalystBrief.kind == "debate",
                    AnalystBrief.persona.in_(DEBATE_LENSES),
                    AnalystBrief.created_at <= observed_at,
                )
                .order_by(AnalystBrief.created_at.desc())
                .limit(30)
            )
        ).scalars().all()
        scores: dict[str, tuple[float, datetime]] = {}
        for row in debate_rows:
            lens = str(row.persona or "")
            if lens in scores:
                continue
            score = _debate_score(row.tools_used)
            if score is not None:
                scores[lens] = (score, row.created_at)
        if set(scores) != DEBATE_LENSES:
            continue
        debate_score = math.fsum(item[0] for item in scores.values()) / len(scores)
        return (
            {
                "news_signal": float(news.sentiment_score),
                "sentiment_debate": debate_score,
            },
            {
                "available": True,
                "fields": ["news_signal", "sentiment_debate"],
                "source": "market_sentiment_snapshots+analyst_briefs",
                "market_slug": slug,
                "news_observed_at": _utc(news.captured_at).isoformat(),
                "debate_observed_at": max(
                    _utc(item[1]) for item in scores.values()
                ).isoformat(),
                "debate_lenses": sorted(scores),
                "backfilled": False,
            },
        )
    return {}, {
        "available": False,
        "reason": "missing_prelock_news_or_scored_debate",
        "backfilled": False,
    }


async def _cross_venue(
    session: AsyncSession,
    slugs: list[str],
    observed_at: datetime,
) -> tuple[dict[str, float], dict[str, Any]]:
    row = await session.scalar(
        select(VenueGap)
        .where(
            or_(VenueGap.pm_slug.in_(slugs), VenueGap.ks_slug.in_(slugs)),
            VenueGap.captured_at <= observed_at,
            VenueGap.stale.is_(False),
        )
        .order_by(VenueGap.abs_gap.desc())
        .limit(1)
    )
    if (
        row is None
        or row.pm_captured_at is None
        or row.ks_captured_at is None
        or _utc(row.pm_captured_at) > observed_at
        or _utc(row.ks_captured_at) > observed_at
    ):
        return {}, {
            "available": False,
            "reason": "missing_prelock_mirrored_venue_quote",
            "backfilled": False,
        }
    return (
        {
            "polymarket_probability": float(row.pm_implied),
            "kalshi_probability": float(row.ks_implied),
        },
        {
            "available": True,
            "fields": ["polymarket_probability", "kalshi_probability"],
            "source": "venue_gaps",
            "pm_slug": row.pm_slug,
            "ks_slug": row.ks_slug,
            "pm_observed_at": _utc(row.pm_captured_at).isoformat(),
            "ks_observed_at": _utc(row.ks_captured_at).isoformat(),
            "backfilled": False,
        },
    )


def _source_slugs(external_market: ExternalMarket) -> list[str]:
    raw = str(external_market.external_id or "").strip()
    candidates = [raw]
    if raw:
        if external_market.platform == Platform.POLYMARKET:
            candidates.append(f"pm-{raw}")
        elif external_market.platform == Platform.KALSHI:
            candidates.append(f"ks-{raw}")
    return list(dict.fromkeys(slug for slug in candidates if slug))


def _debate_score(tools_used: object) -> float | None:
    if not isinstance(tools_used, list):
        return None
    for item in tools_used:
        if not isinstance(item, dict):
            continue
        value = item.get("sentiment_score")
        if isinstance(value, bool):
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(score) and -1.0 <= score <= 1.0:
            return score
    return None


def _availability(
    available: bool,
    *,
    fields: tuple[str, ...],
    source: str,
    backfilled: bool,
) -> dict[str, Any]:
    if not available:
        return {
            "available": False,
            "reason": "missing_forecast_columns",
            "backfilled": backfilled,
        }
    return {
        "available": True,
        "fields": list(fields),
        "source": source,
        "backfilled": backfilled,
    }


def _probability(value: object | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    return probability if 0.0 <= probability <= 1.0 else None


def _number(value: object | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
