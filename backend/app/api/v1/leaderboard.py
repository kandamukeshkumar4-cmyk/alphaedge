from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse

router = APIRouter(tags=["leaderboard"])


def _display_username(email: str | None, rank: int) -> str:
    if email:
        local = email.split("@", 1)[0].strip()
        if local:
            return local
    return f"Trader #{rank}"


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(db: AsyncSession = Depends(get_db)) -> LeaderboardResponse:
    entries: list[LeaderboardEntry] = []
    try:
        result = await db.execute(
            text(
                """
                SELECT
                    po.user_id,
                    u.email,
                    SUM(
                        CASE
                            WHEN po.settled IS TRUE
                                 AND UPPER(po.outcome) = COALESCE(mr.outcome, '')
                            THEN po.shares * 1.0 - po.cost
                            WHEN po.settled IS TRUE THEN 0.0 - po.cost
                            ELSE 0.0
                        END
                    ) AS realized_pnl,
                    COUNT(*) AS total_trades,
                    SUM(
                        CASE
                            WHEN po.settled IS TRUE
                                 AND UPPER(po.outcome) = COALESCE(mr.outcome, '')
                            THEN 1
                            ELSE 0
                        END
                    ) AS wins,
                    SUM(CASE WHEN po.settled IS TRUE THEN 1 ELSE 0 END) AS settled_trades
                FROM paper_orders po
                LEFT JOIN market_resolutions mr ON mr.slug = po.slug
                LEFT JOIN users u ON u.id = po.user_id
                GROUP BY po.user_id, u.email
                ORDER BY realized_pnl DESC
                LIMIT 20
                """
            )
        )
        rows = result.mappings().all()
        for rank, row in enumerate(rows, start=1):
            settled = int(row["settled_trades"] or 0)
            wins = int(row["wins"] or 0)
            win_rate = round(wins / settled, 4) if settled > 0 else 0.0
            entries.append(
                LeaderboardEntry(
                    rank=rank,
                    username=_display_username(
                        str(row["email"]) if row["email"] is not None else None,
                        rank,
                    ),
                    realized_pnl=round(float(row["realized_pnl"] or 0.0), 4),
                    total_trades=int(row["total_trades"] or 0),
                    win_rate=win_rate,
                )
            )
    except (OperationalError, ProgrammingError):
        entries = []

    return LeaderboardResponse(entries=entries)
