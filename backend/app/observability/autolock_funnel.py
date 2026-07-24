"""Staged counts for the forecast-autolock eligibility funnel (Loop V33 B2'b).

Loop V33 B1 could only diagnose the funnel by reaching into the DB directly: the
worker recorded `candidates`/`locked`/`skipped` but never *why* a market wasn't a
candidate, so an empty input set was indistinguishable from a working loop with
nothing to do — prod showed `forecast_autolock` alive and `status=ok` for months
while it selected exactly nothing.

This module makes that visible. It runs the same filter chain as
``app.workers.forecast_autolock`` as staged counts, and starts at stage 0 (total
rows in ``external_markets``) because a starved input set is invisible if you
begin the funnel at ``status == OPEN``.

Read-only: SELECT COUNT(*) only. No writes, no order path, no
PAPER_TRADING_ONLY interaction.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
)

STAGE_NAMES: tuple[str, ...] = (
    "0_external_markets_total",
    "1_status_open",
    "2_has_close_at",
    "3_close_at_in_future",
    "4_within_horizon",
    "5_lacks_live_forecast",
    "6_after_batch_cap",
)


async def _count(session: AsyncSession, *where) -> int:
    stmt = select(func.count()).select_from(ExternalMarket)
    for clause in where:
        stmt = stmt.where(clause)
    return int((await session.execute(stmt)).scalar_one())


async def funnel_snapshot(
    session: AsyncSession,
    *,
    now: datetime,
    limit: int,
    window_sec: int,
) -> dict[str, object]:
    """Stage-by-stage counts for the autolock eligibility query.

    ``limit`` / ``window_sec`` are expected to be already bounded by the caller
    the same way the worker bounds them, so the counts describe what that worker
    would really select.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    horizon = now + timedelta(seconds=window_sec)

    live_forecast_exists = (
        select(ForecastLog.id)
        .where(
            ForecastLog.external_market_id == ExternalMarket.id,
            ForecastLog.mode == ForecastMode.LIVE,
        )
        .exists()
    )

    open_ = ExternalMarket.status == ExternalMarketStatus.OPEN
    has_close = ExternalMarket.close_at.is_not(None)
    pre_close = ExternalMarket.close_at > now
    in_horizon = ExternalMarket.close_at <= horizon
    no_live = ~live_forecast_exists

    counts = [
        await _count(session),
        await _count(session, open_),
        await _count(session, open_, has_close),
        await _count(session, open_, has_close, pre_close),
        await _count(session, open_, has_close, pre_close, in_horizon),
        await _count(session, open_, has_close, pre_close, in_horizon, no_live),
    ]
    counts.append(min(counts[-1], limit))
    stages = dict(zip(STAGE_NAMES, counts, strict=True))

    drops = [
        {
            "from": STAGE_NAMES[i],
            "to": STAGE_NAMES[i + 1],
            "excluded": counts[i] - counts[i + 1],
            "remaining": counts[i + 1],
        }
        for i in range(len(counts) - 1)
    ]

    # An empty input set makes every downstream drop 0, which would otherwise
    # read as "no filter excludes anything" — the opposite of the truth. Say so.
    input_starved = counts[0] == 0

    return {
        "stages": stages,
        "drops": drops,
        "input_starved": input_starved,
        "eligible": counts[5],
        "selectable": counts[6],
        "biggest_exclusion": (
            "INPUT_STARVED: external_markets is empty; no filter can be the "
            "binding constraint because the worker sees no rows at all"
            if input_starved
            else max(drops, key=lambda d: d["excluded"])
        ),
    }


def funnel_detail(snapshot: dict[str, object]) -> str:
    """One-line human summary for a loop heartbeat's ``detail`` field."""
    if snapshot.get("input_starved"):
        return "input starved: external_markets is empty (0 candidates possible)"
    stages: dict[str, int] = snapshot["stages"]  # type: ignore[assignment]
    biggest = snapshot.get("biggest_exclusion")
    parts = [
        f"external={stages['0_external_markets_total']}",
        f"open={stages['1_status_open']}",
        f"has_close={stages['2_has_close_at']}",
        f"pre_close={stages['3_close_at_in_future']}",
        f"in_horizon={stages['4_within_horizon']}",
        f"lacks_live={stages['5_lacks_live_forecast']}",
        f"selectable={stages['6_after_batch_cap']}",
    ]
    if isinstance(biggest, dict) and biggest.get("excluded"):
        parts.append(f"biggest_drop={biggest['from']}->{biggest['to']}:{biggest['excluded']}")
    return " ".join(parts)
