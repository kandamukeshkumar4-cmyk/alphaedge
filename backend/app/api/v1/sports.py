"""Sports results API — ESPN NBA scoreboard signals (Workstream C).

READ-ONLY signal input. Does NOT resolve or settle markets.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.security import verify_admin_api_key
from app.data.connectors.sports_results import (
    SOURCE,
    SPORTS_RESULT_SIGNAL_TYPE,
    SportsResultsConnector,
    games_to_signal_events,
)
from app.db.models import SignalEvent

router = APIRouter(prefix="/api/v1/sports", tags=["sports"])
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


class SportsResultsOut(BaseModel):
    date: str | None
    source: str
    games: list[GameResultOut]
    finals: int
    paper_trading_only: bool = True
    resolves_markets: bool = False


class SportsIngestOut(BaseModel):
    date: str | None
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


@router.get("/results", response_model=SportsResultsOut)
async def list_sports_results(
    game_date: str | None = Query(default=None, alias="date"),
) -> SportsResultsOut:
    """Fetch NBA scoreboard rows (signals only — never resolves markets)."""
    parsed = _parse_optional_date(game_date)
    try:
        connector = SportsResultsConnector()
        games = await asyncio.to_thread(connector.fetch_games, parsed)
    except Exception:  # noqa: BLE001 — honest-empty degrade, never 5xx
        logger.warning("sports_results upstream fetch failed", exc_info=True)
        games = []

    return SportsResultsOut(
        date=parsed.isoformat() if isinstance(parsed, date) else game_date,
        source=SOURCE,
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
            )
            for g in games
        ],
        finals=sum(1 for g in games if g.status == "final"),
    )


@router.post("/ingest", response_model=SportsIngestOut)
async def ingest_sports_results(
    game_date: str | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_api_key),
) -> SportsIngestOut:
    """Persist final-game sports:result SignalEvents (no market resolution)."""
    parsed = _parse_optional_date(game_date)
    try:
        connector = SportsResultsConnector()
        games = await asyncio.to_thread(connector.fetch_games, parsed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sports_results ingest fetch failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="upstream sports results unavailable") from exc

    event_dicts = games_to_signal_events(games)
    inserted = await persist_sports_signal_events(session, event_dicts)
    await session.commit()
    return SportsIngestOut(
        date=parsed.isoformat() if isinstance(parsed, date) else game_date,
        fetched=len(games),
        finals=sum(1 for g in games if g.status == "final"),
        inserted=inserted,
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
    rows = (
        await session.execute(
            select(SignalEvent.platform, SignalEvent.market_id, SignalEvent.payload).where(
                SignalEvent.signal_type == SPORTS_RESULT_SIGNAL_TYPE,
                SignalEvent.platform == SOURCE,
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
