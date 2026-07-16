"""Public LIVE ForecastLog read for market detail lock chip (Loop V48 U1).

``GET /api/v1/markets/{slug}/locked-forecast`` — read-only, no auth, no order
path. Returns the locked LIVE ledger row for a market (autolock / system
forecaster), never a fresh XGBoost call. Works for live ``pm-`` / ``ks-`` slugs
and catalog slugs that share the bridge identity (``ExternalMarket.external_id``
== venue slug / ``Market.external_slug``).

When no LIVE lock exists: honest empty shape (``locked=false``,
``empty_reason=pre_lock``) — never invent a probability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    ExternalMarket,
    ForecastLog,
    ForecastMode,
    Market,
    OddsSnapshot,
)
from app.db.session import get_db
from app.schemas.market import LockedForecastResponse
from app.workers.forecast_autolock import AUTOLOCK_FORECASTER_ID

router = APIRouter(prefix="/api/v1", tags=["markets"])
settings = get_settings()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _float_or_none(value: object | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _venue_identity_candidates(slug: str) -> list[str]:
    """Map a public market slug to possible ExternalMarket.external_id values.

    Bridge + autolock key on venue identity (Gamma slug / Kalshi ticker), which
    live ingest stores as ``Market.external_slug`` and prefixes with ``pm-`` /
    ``ks-`` for the local catalog slug.
    """
    raw = (slug or "").strip()
    if not raw:
        return []
    out: list[str] = [raw]
    lower = raw.lower()
    if lower.startswith("pm-") and len(raw) > 3:
        out.append(raw[3:])
    elif lower.startswith("ks-") and len(raw) > 3:
        out.append(raw[3:])
    # de-dupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in out:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _local_slug_candidates(slug: str, external_id: str | None) -> list[str]:
    """Odds / catalog rows may be keyed by local pm-/ks- slug or raw venue id."""
    raw = (slug or "").strip()
    out: list[str] = []
    for item in (raw, external_id):
        if item:
            out.append(item)
    if external_id:
        out.append(f"pm-{external_id}")
        out.append(f"ks-{external_id}")
    seen: set[str] = set()
    unique: list[str] = []
    for item in out:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


async def _resolve_external_market(
    db: AsyncSession, slug: str
) -> tuple[ExternalMarket | None, str | None]:
    """Return (ExternalMarket, external_id identity) for the request slug."""
    identities = _venue_identity_candidates(slug)

    market_row = await db.scalar(select(Market).where(Market.slug == slug).limit(1))
    if market_row is not None and market_row.external_slug:
        ext_slug = str(market_row.external_slug).strip()
        if ext_slug and ext_slug not in identities:
            identities.append(ext_slug)

    if not identities:
        return None, None

    external = await db.scalar(
        select(ExternalMarket)
        .where(ExternalMarket.external_id.in_(identities))
        .limit(1)
    )
    if external is not None:
        return external, external.external_id
    return None, identities[0] if identities else None


async def _latest_live_forecast(
    db: AsyncSession, external_market_id: UUID
) -> ForecastLog | None:
    """Latest LIVE ForecastLog for the market (prefer system autolock row)."""
    # Prefer the system autolock forecaster — that is the model lock chip source.
    autolock_row = await db.scalar(
        select(ForecastLog)
        .where(
            ForecastLog.external_market_id == external_market_id,
            ForecastLog.mode == ForecastMode.LIVE,
            ForecastLog.forecaster_id == AUTOLOCK_FORECASTER_ID,
        )
        .order_by(ForecastLog.locked_at.desc(), ForecastLog.seq.desc())
        .limit(1)
    )
    if autolock_row is not None:
        return autolock_row
    # Fall back to any LIVE row (blocks further autolock; still a real lock).
    return await db.scalar(
        select(ForecastLog)
        .where(
            ForecastLog.external_market_id == external_market_id,
            ForecastLog.mode == ForecastMode.LIVE,
        )
        .order_by(ForecastLog.locked_at.desc(), ForecastLog.seq.desc())
        .limit(1)
    )


async def _current_market_probability(
    db: AsyncSession, slug: str, external_id: str | None
) -> float | None:
    slugs = _local_slug_candidates(slug, external_id)
    if not slugs:
        return None
    value = await db.scalar(
        select(OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug.in_(slugs))
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    return _float_or_none(value)


def _empty_response(
    slug: str,
    *,
    current_market_probability: float | None,
    external_market_id: UUID | None = None,
) -> LockedForecastResponse:
    return LockedForecastResponse(
        slug=slug,
        locked=False,
        user_probability=None,
        locked_at=None,
        market_implied_at_lock=None,
        current_market_probability=current_market_probability,
        mode=None,
        provisional=True,
        paper_trading_only=settings.paper_trading_only,
        forecast_id=None,
        external_market_id=external_market_id,
        empty_reason="pre_lock",
    )


@router.get(
    "/markets/{slug}/locked-forecast",
    response_model=LockedForecastResponse,
)
async def get_locked_forecast(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> LockedForecastResponse:
    """Public read-only LIVE ForecastLog for a market slug."""
    external, identity = await _resolve_external_market(db, slug)
    current_p = await _current_market_probability(
        db, slug, identity or (external.external_id if external else None)
    )

    if external is None:
        return _empty_response(slug, current_market_probability=current_p)

    forecast = await _latest_live_forecast(db, external.id)
    if forecast is None:
        return _empty_response(
            slug,
            current_market_probability=current_p,
            external_market_id=external.id,
        )

    meta = forecast.snapshot_metadata or {}
    provisional = bool(meta.get("model_provisional", True))
    locked_at = _as_utc(forecast.locked_at)

    return LockedForecastResponse(
        slug=slug,
        locked=True,
        user_probability=_float_or_none(forecast.user_probability),
        locked_at=locked_at,
        market_implied_at_lock=_float_or_none(forecast.market_implied_probability),
        current_market_probability=current_p,
        mode=forecast.mode.value if forecast.mode is not None else "live",
        provisional=provisional,
        paper_trading_only=settings.paper_trading_only,
        forecast_id=forecast.id,
        external_market_id=external.id,
        empty_reason=None,
    )
