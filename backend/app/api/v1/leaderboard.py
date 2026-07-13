"""Public paper-trading leaderboard (Loop V15 B1).

Completes the existing ranked surface: ROI, offset/limit pagination, in-process
TTL cache, anonymized display names, stable tie-break. Ranking math lives in
``analytics_leaderboard`` so unit tests cover ties / zero-settled / negative ROI
without hitting the DB.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import leaderboard_cache
from app.db.session import get_db
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse
from app.services.analytics_leaderboard import (
    DEFAULT_LIMIT,
    LEADERBOARD_AGG_SQL,
    LEADERBOARD_TTL_SEC,
    MAX_LIMIT,
    LeaderboardRow,
    SortKey,
    rank_rows,
)

router = APIRouter(tags=["leaderboard"])


def _rows_from_mappings(mappings: list) -> list[LeaderboardRow]:
    rows: list[LeaderboardRow] = []
    for row in mappings:
        rows.append(
            LeaderboardRow(
                user_id=UUID(str(row["user_id"])),
                display_name=str(row["display_name"]) if row["display_name"] else None,
                realized_pnl=float(row["realized_pnl"] or 0.0),
                total_cost=float(row["total_cost"] or 0.0),
                total_trades=int(row["total_trades"] or 0),
                wins=int(row["wins"] or 0),
                settled_trades=int(row["settled_trades"] or 0),
            )
        )
    return rows


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    sort: SortKey = Query(default="realized_pnl"),
) -> LeaderboardResponse:
    cache_key = ("leaderboard", sort, limit, offset)
    cached = leaderboard_cache.get(cache_key, LEADERBOARD_TTL_SEC)
    if cached is not None:
        return LeaderboardResponse(**cached, cached=True)

    entries: list[LeaderboardEntry] = []
    total = 0
    try:
        result = await db.execute(text(LEADERBOARD_AGG_SQL))
        mappings = result.mappings().all()
        ranked, total = rank_rows(
            _rows_from_mappings(list(mappings)),
            sort=sort,
            limit=limit,
            offset=offset,
        )
        entries = [
            LeaderboardEntry(
                rank=e.rank,
                username=e.username,
                realized_pnl=e.realized_pnl,
                total_trades=e.total_trades,
                win_rate=e.win_rate,
                roi=e.roi,
            )
            for e in ranked
        ]
        body = LeaderboardResponse(
            entries=entries,
            limit=limit,
            offset=offset,
            total=total,
            sort=sort,
            cached=False,
        )
        # Only cache successful DB builds — never poison TTL with error empties.
        leaderboard_cache.put(
            cache_key,
            {
                "entries": [e.model_dump() for e in body.entries],
                "limit": body.limit,
                "offset": body.offset,
                "total": body.total,
                "sort": body.sort,
            },
        )
        return body
    except (OperationalError, ProgrammingError):
        return LeaderboardResponse(
            entries=[],
            limit=limit,
            offset=offset,
            total=0,
            sort=sort,
            cached=False,
        )
