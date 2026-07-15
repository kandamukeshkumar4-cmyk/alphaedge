"""Sports results API — multi-league ESPN scoreboard signals (Workstream C / Loop V31).

READ-ONLY signal input. Does NOT resolve or settle markets.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.security import verify_admin_api_key
from app.data.connectors.http import SourceHealth, refresh_source_health
from app.data.connectors.sports_results import (
    DEFAULT_LEAGUE,
    SOURCE,
    SPORTS_RESULT_SIGNAL_TYPE,
    SUPPORTED_LEAGUES,
    SportsResultsConnector,
    games_to_signal_events,
    get_league_spec,
    is_league_enabled,
    parse_enabled_leagues,
    source_for_league,
)
from app.db.models import SignalEvent

router = APIRouter(prefix="/api/v1/sports", tags=["sports"])
sources_router = APIRouter(
    prefix="/api/v1/system",
    tags=["system"],
    dependencies=[Depends(verify_admin_api_key)],
)
logger = logging.getLogger(__name__)


class GameResultOut(BaseModel):
    event_id: str
    game_date: str
    home_team: str
    away_team: str
    home_abbr: str
    away_abbr: str
    home_score: int | None
    away_score: int | None
    status: str
    status_detail: str
    source: str
    league: str = DEFAULT_LEAGUE


class SportsResultsOut(BaseModel):
    date: str | None
    league: str = DEFAULT_LEAGUE
    source: str
    games: list[GameResultOut]
    finals: int
    paper_trading_only: bool = True
    resolves_markets: bool = False


class SportsIngestOut(BaseModel):
    date: str | None
    league: str = DEFAULT_LEAGUE
    fetched: int
    finals: int
    inserted: int
    signal_type: str = SPORTS_RESULT_SIGNAL_TYPE
    source: str = SOURCE
    paper_trading_only: bool = True
    resolves_markets: bool = False
    disclaimer: str = Field(
        default=(
            "READ-ONLY sports result signals persisted. Does NOT resolve or settle markets."
        )
    )


def _resolve_league(league: str | None, *, require_enabled: bool = True) -> str:
    """Validate league key; default nba. Unknown/disabled → 422 (additive API).

    When ``require_enabled`` is True (default), the league must appear in
    ``SPORTS_LEAGUES_ENABLED`` so the poll path only serves gated leagues.
    """
    key = (league or DEFAULT_LEAGUE).strip().lower() or DEFAULT_LEAGUE
    try:
        resolved = get_league_spec(key).key
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"league must be one of: {', '.join(SUPPORTED_LEAGUES)}",
        ) from exc
    if require_enabled and not is_league_enabled(resolved):
        enabled = parse_enabled_leagues()
        raise HTTPException(
            status_code=422,
            detail=(
                f"league {resolved!r} is not enabled; "
                f"SPORTS_LEAGUES_ENABLED={','.join(enabled)}"
            ),
        )
    return resolved


@router.get("/results", response_model=SportsResultsOut)
async def list_sports_results(
    game_date: str | None = Query(default=None, alias="date"),
    league: str = Query(default=DEFAULT_LEAGUE, description="League key (default nba)"),
) -> SportsResultsOut:
    """Fetch scoreboard rows for a league (signals only — never resolves markets)."""
    resolved = _resolve_league(league)
    parsed = _parse_optional_date(game_date)
    try:
        connector = SportsResultsConnector(league=resolved)
        games = await asyncio.to_thread(connector.fetch_games, parsed)
    except Exception:  # noqa: BLE001 — honest-empty degrade, never 5xx
        logger.warning(
            "sports_results upstream fetch failed league=%s", resolved, exc_info=True
        )
        games = []

    return SportsResultsOut(
        date=parsed.isoformat() if isinstance(parsed, date) else game_date,
        league=resolved,
        source=source_for_league(resolved),
        games=[
            GameResultOut(
                event_id=g.event_id,
                game_date=g.game_date,
                home_team=g.home_team,
                away_team=g.away_team,
                home_abbr=g.home_abbr,
                away_abbr=g.away_abbr,
                home_score=g.home_score,
                away_score=g.away_score,
                status=g.status,
                status_detail=g.status_detail,
                source=g.source,
                league=g.league,
            )
            for g in games
        ],
        finals=sum(1 for g in games if g.status == "final"),
    )


@router.post("/ingest", response_model=SportsIngestOut)
async def ingest_sports_results(
    game_date: str | None = Query(default=None, alias="date"),
    league: str = Query(default=DEFAULT_LEAGUE, description="League key (default nba)"),
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_api_key),
) -> SportsIngestOut:
    """Persist final-game sports:result SignalEvents (no market resolution)."""
    resolved = _resolve_league(league)
    parsed = _parse_optional_date(game_date)
    try:
        connector = SportsResultsConnector(league=resolved)
        games = await asyncio.to_thread(connector.fetch_games, parsed)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sports_results ingest fetch failed league=%s: %s",
            resolved,
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail="upstream sports results unavailable") from exc

    event_dicts = games_to_signal_events(games)
    inserted = await persist_sports_signal_events(session, event_dicts)
    await session.commit()
    return SportsIngestOut(
        date=parsed.isoformat() if isinstance(parsed, date) else game_date,
        league=resolved,
        fetched=len(games),
        finals=sum(1 for g in games if g.status == "final"),
        inserted=inserted,
        source=source_for_league(resolved),
    )


async def persist_sports_signal_events(
    session: AsyncSession,
    event_dicts: list[dict[str, Any]],
) -> int:
    """Insert SignalEvents, skipping duplicates by (platform, market_id, event_id)."""
    if not event_dicts:
        return 0

    existing_keys = await _existing_event_keys(session)
    inserted = 0
    for row in event_dicts:
        payload = row.get("payload") or {}
        event_id = str(payload.get("event_id") or "")
        key = (row["platform"], row["market_id"], event_id)
        if key in existing_keys:
            continue
        session.add(
            SignalEvent(
                signal_type=row["signal_type"],
                platform=row["platform"],
                market_id=row["market_id"],
                headline_eligible=bool(row.get("headline_eligible", False)),
                payload=payload,
            )
        )
        existing_keys.add(key)
        inserted += 1
    return inserted


async def _existing_event_keys(session: AsyncSession) -> set[tuple[str, str, str]]:
    # All sports platforms (espn-nba, espn-nfl, …) — not only the NBA default source.
    rows = (
        await session.execute(
            select(SignalEvent.platform, SignalEvent.market_id, SignalEvent.payload).where(
                SignalEvent.signal_type == SPORTS_RESULT_SIGNAL_TYPE,
            )
        )
    ).all()
    keys: set[tuple[str, str, str]] = set()
    for platform, market_id, payload in rows:
        event_id = ""
        if isinstance(payload, dict):
            event_id = str(payload.get("event_id") or "")
        keys.add((str(platform), str(market_id), event_id))
    return keys


def _parse_optional_date(raw: str | None) -> date | None:
    if raw is None or raw == "":
        return None
    try:
        if len(raw) == 8 and raw.isdigit():
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


class SourceHealthOut(BaseModel):
    source: str
    state: str
    consecutive_failures: int
    total_successes: int
    total_failures: int
    last_error: str | None = None
    last_success_age_sec: float | None = None
    circuit_open_remaining_sec: float | None = None


class SourcesOut(BaseModel):
    sources: list[SourceHealthOut]
    count: int
    paper_trading_only: bool = True


def serialize_source_health(row: SourceHealth, *, now: float | None = None) -> SourceHealthOut:
    """Map a SourceHealth registry row to the admin API shape."""
    clock = time.monotonic() if now is None else now
    age: float | None = None
    if row.last_success_at is not None:
        age = round(max(0.0, clock - row.last_success_at), 3)
    remaining: float | None = None
    if row.open_until is not None:
        remaining = round(max(0.0, row.open_until - clock), 3)
    return SourceHealthOut(
        source=row.source,
        state=row.state,
        consecutive_failures=row.consecutive_failures,
        total_successes=row.total_successes,
        total_failures=row.total_failures,
        last_error=row.last_error,
        last_success_age_sec=age,
        circuit_open_remaining_sec=remaining,
    )


@sources_router.get("/sources", response_model=SourcesOut)
async def list_connector_sources() -> SourcesOut:
    """Admin-gated per-connector health from the C1 get_source_health registry.

    Requires ``X-Admin-API-Key`` (same pattern as ``/admin/observability/*``).
    Read-only — no order path, no fabricated counters.
    """
    from app.core.config import get_settings

    now = time.monotonic()
    registry = refresh_source_health(monotonic=lambda: now)
    rows = [
        serialize_source_health(registry[name], now=now)
        for name in sorted(registry.keys())
    ]
    return SourcesOut(
        sources=rows,
        count=len(rows),
        paper_trading_only=get_settings().paper_trading_only,
    )
