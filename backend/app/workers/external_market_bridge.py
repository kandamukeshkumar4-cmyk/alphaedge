"""Register ingested venue catalog markets as ExternalMarket rows (Loop V33 B2').

Loop V33 B1 measured the forecast-autolock funnel and found it INPUT-STARVED:
``external_markets`` had exactly one writer (``ExternalMarketService.resolve_url*``,
reachable only from the forecaster-driven routes), while the live-ingest loop
writes only the ``markets`` catalog. 99 real ingested markets produced 0 autolock
candidates. This worker is the missing supply bridge: it registers eligible
*already-ingested* venue markets as ``ExternalMarket`` rows so the existing
autolock → venue-resolve → score chain finally has input.

It feeds the input. It does NOT touch the gates:

- It never locks a forecast, never scores, never resolves.
- It never writes ``winning_outcome`` / ``resolved_at`` — resolution stays
  exclusively with the venue resolver.
- It only registers markets the venue itself reports as open with a genuine
  FUTURE close time, re-read live from the venue adapter rather than trusted
  from the catalog. Everything else is excluded (when in doubt, exclude).

Identity is the sharp edge here. The catalog's ``Market.external_id`` column is
NOT the venue identity the resolver reads: live ingest stores Polymarket's
``conditionId`` and Kalshi's *event* ticker there, while both venue adapters'
``normalize()`` key on the Gamma **slug** / market **ticker** — which ingest puts
in ``Market.external_slug``. Bridging on ``external_id`` would register rows the
resolver can never settle, or worse, settle against the wrong market. So this
worker keys on ``external_slug``, then proves the identity round-trips through
both the venue adapter and ``parse_market_url`` before inserting anything.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    JobRun,
    Market,
    MarketStatus,
    Platform,
)
from app.forecasting.market_source import parse_market_url
from app.services.venues.registry import get_venue_adapter

logger = logging.getLogger(__name__)

EXTERNAL_MARKET_BRIDGE_JOB_NAME = "external_market_bridge_task"
DEFAULT_BRIDGE_BATCH_SIZE = 25
MAX_BRIDGE_BATCH_SIZE = 250

# Catalog ``source`` values that are real venues backed by a resolver adapter.
# Anything else — notably the "seed" default — is synthetic demo data and MUST
# NEVER be bridged: a forecast on it could never be graded against a real
# outcome, which is exactly the fabrication this loop exists to prevent.
_VENUE_SOURCES: dict[str, Platform] = {
    "polymarket": Platform.POLYMARKET,
    "kalshi": Platform.KALSHI,
}

# Venue-reported lifecycle strings that mean "not safely pre-close". Mirrors the
# autolock worker's terminal set so the two agree on what "open" means.
_TERMINAL_VENUE_STATUSES = frozenset(
    {"closed", "resolved", "settled", "finalized", "determined", "ended"}
)

_VENUE_URL_TEMPLATES: dict[Platform, str] = {
    Platform.POLYMARKET: "https://polymarket.com/event/{external_id}",
    Platform.KALSHI: "https://kalshi.com/markets/{external_id}",
}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _venue_reports_open(status: str | None) -> bool:
    return str(status or "").strip().lower() not in _TERMINAL_VENUE_STATUSES


async def bridge_external_markets(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_BRIDGE_BATCH_SIZE,
) -> dict[str, int]:
    """Register a bounded batch of eligible ingested venue markets.

    Returns ``candidates`` / ``bridged`` / ``skipped`` / ``errors``.
    Idempotent: a market already present in ``external_markets`` is filtered out
    in SQL, so a re-run neither duplicates it nor spends the batch budget on it.
    """
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    bounded_limit = min(max(int(limit), 1), MAX_BRIDGE_BATCH_SIZE)

    # Idempotency pre-filter. Matching on external_id alone (rather than the
    # (platform, external_id) pair) keeps this portable across the pg enum and
    # the SQLite test backend. It is deliberately conservative: the worst case
    # is skipping a market whose id collides across venues — a coverage miss,
    # never a duplicate row or a wrong-market registration. The exact
    # (platform, external_id) check still runs per row before insert.
    already_bridged = (
        select(ExternalMarket.id)
        .where(ExternalMarket.external_id == Market.external_slug)
        .exists()
    )
    candidates = (
        (
            await session.execute(
                select(Market)
                .where(
                    Market.source.in_(tuple(_VENUE_SOURCES)),
                    Market.status == MarketStatus.OPEN,
                    Market.external_slug.is_not(None),
                    Market.external_slug != "",
                    # A market with no close time can never be proven pre-close.
                    Market.lock_at.is_not(None),
                    Market.lock_at > now,
                    ~already_bridged,
                )
                .order_by(Market.lock_at.asc(), Market.id.asc())
                .limit(bounded_limit)
            )
        )
        .scalars()
        .all()
    )

    bridged = skipped = errors = 0
    for market in candidates:
        try:
            platform = _VENUE_SOURCES[market.source]
            catalog_identity = str(market.external_slug or "").strip()

            # Re-read the market from the venue the resolver will later use. If
            # the resolver cannot fetch it now, it could never settle a forecast
            # on it, so it must not become a candidate.
            venue = get_venue_adapter(market.source).fetch_market(catalog_identity)
            if venue is None:
                skipped += 1
                continue

            # Never bridge anything the venue reports as settled or terminal —
            # resolution is the resolver's job, and a past-close market can never
            # take an honest pre-close forecast.
            if (
                venue.resolved
                or venue.winning_outcome is not None
                or not _venue_reports_open(venue.status)
            ):
                skipped += 1
                continue

            # The venue's own close time is authoritative; the catalog's lock_at
            # is a possibly-stale copy. Require a genuine FUTURE close.
            close_at = venue.close_time
            if close_at is None or _as_utc(close_at) <= now:
                skipped += 1
                continue

            # Identity round-trip. Build the canonical URL from the venue's own
            # normalized id and parse it back with the SAME parser the forecast
            # path uses, so a human forecast on this market resolves to this row
            # instead of creating a duplicate. parse_market_url lowercases, and
            # both Kalshi adapters upper-case their input, so the canonical
            # lowercase id resolves on the autolock and resolver paths alike.
            venue_identity = str(venue.external_id or "").strip()
            template = _VENUE_URL_TEMPLATES.get(platform)
            if not venue_identity or template is None:
                skipped += 1
                continue
            parsed = parse_market_url(template.format(external_id=venue_identity))
            if (
                parsed is None
                or parsed.platform is not platform
                or parsed.external_id.lower() != venue_identity.lower()
            ):
                skipped += 1
                continue

            # Exact idempotency check on the real unique key.
            exists = (
                await session.execute(
                    select(ExternalMarket.id).where(
                        ExternalMarket.platform == platform,
                        ExternalMarket.external_id == parsed.external_id,
                    )
                )
            ).first()
            if exists is not None:
                skipped += 1
                continue

            async with session.begin_nested():
                session.add(
                    ExternalMarket(
                        platform=platform,
                        external_id=parsed.external_id,
                        url=parsed.canonical_url,
                        title=(venue.title or market.title or venue_identity)[:256],
                        category=market.category,
                        status=ExternalMarketStatus.OPEN,
                        close_at=close_at,
                        # winning_outcome / resolved_at intentionally left unset:
                        # only the venue resolver may ever populate them.
                    )
                )
            bridged += 1
        except Exception as exc:  # noqa: BLE001 - isolate each catalog market
            logger.warning(
                "external market bridge failed for %s/%s: %s",
                market.source,
                market.external_slug,
                exc,
            )
            errors += 1

    return {
        "candidates": len(candidates),
        "bridged": bridged,
        "skipped": skipped,
        "errors": errors,
    }


def bridge_detail(summary: dict[str, Any] | None) -> str | None:
    """One-line public heartbeat detail for a bridge pass (Loop V49 E4).

    Symmetric to autolock's ``funnel_detail``: exposes per-pass
    candidates/bridged/skipped/errors without an admin key so
    "bridge is alive but bridging nothing" is visible on
    ``GET /api/v1/system/loops``.
    """
    if summary is None or not isinstance(summary, dict):
        return None
    # Disabled-pass shape from the ARQ entrypoint (no counters).
    if summary.get("skipped") is True and "candidates" not in summary:
        reason = summary.get("reason") or "bridge disabled"
        return f"disabled: {reason}"
    try:
        return (
            f"candidates={int(summary.get('candidates', 0))} "
            f"bridged={int(summary.get('bridged', 0))} "
            f"skipped={int(summary.get('skipped', 0))} "
            f"errors={int(summary.get('errors', 0))}"
        )
    except (TypeError, ValueError):
        return None


async def external_market_bridge_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint with a durable JobRun heartbeat for every enabled pass."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    if not settings.scheduler_external_market_bridge_enabled:
        return {
            "skipped": True,
            "reason": "SCHEDULER_EXTERNAL_MARKET_BRIDGE_ENABLED=false",
        }

    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    now = ctx.get("now")
    limit = int(ctx.get("limit", settings.external_market_bridge_batch))
    async with session_factory() as session:
        try:
            summary = await bridge_external_markets(session, now=now, limit=limit)
            session.add(
                JobRun(
                    job_name=EXTERNAL_MARKET_BRIDGE_JOB_NAME,
                    status="degraded" if summary["errors"] else "success",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            return summary
        except Exception as exc:
            await session.rollback()
            session.add(
                JobRun(
                    job_name=EXTERNAL_MARKET_BRIDGE_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
