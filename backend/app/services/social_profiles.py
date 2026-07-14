"""Public trader profile aggregation for the paper-trading social layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_leaderboard import anonymized_username, roi, win_rate

PUBLIC_TRADER_PROFILE_SQL = """
SELECT
    u.id AS user_id,
    u.display_name,
    u.created_at,
    COUNT(po.id) AS total_trades,
    COALESCE(SUM(CASE WHEN po.settled IS TRUE THEN po.cost ELSE 0.0 END), 0.0)
        AS total_cost,
    COALESCE(SUM(
        CASE
            WHEN po.settled IS TRUE
                 AND UPPER(po.outcome) = COALESCE(UPPER(mr.outcome), '')
            THEN po.shares * 1.0 - po.cost
            WHEN po.settled IS TRUE THEN 0.0 - po.cost
            ELSE 0.0
        END
    ), 0.0) AS realized_pnl,
    COALESCE(SUM(
        CASE
            WHEN po.settled IS TRUE
                 AND UPPER(po.outcome) = COALESCE(UPPER(mr.outcome), '')
            THEN 1
            ELSE 0
        END
    ), 0) AS wins,
    COALESCE(SUM(CASE WHEN po.settled IS TRUE THEN 1 ELSE 0 END), 0)
        AS settled_trades,
    (SELECT COUNT(*) FROM follows f WHERE f.followee_id = u.id) AS followers_count,
    (SELECT COUNT(*) FROM follows f WHERE f.follower_id = u.id) AS following_count
FROM users u
LEFT JOIN paper_orders po ON po.user_id = u.id
LEFT JOIN market_resolutions mr ON mr.slug = po.slug
WHERE u.profile_public IS TRUE
GROUP BY u.id, u.display_name, u.created_at
"""


@dataclass(frozen=True)
class PublicTraderProfile:
    user_id: UUID
    username: str
    member_since: datetime
    trade_count: int
    settled_trade_count: int
    win_rate: float
    roi: float
    followers_count: int
    following_count: int


def _profile_from_row(row) -> PublicTraderProfile:
    user_id = UUID(str(row["user_id"]))
    display_name = str(row["display_name"]) if row["display_name"] else None
    total_trades = int(row["total_trades"] or 0)
    settled_trades = int(row["settled_trades"] or 0)
    realized_pnl = float(row["realized_pnl"] or 0.0)
    total_cost = float(row["total_cost"] or 0.0)
    return PublicTraderProfile(
        user_id=user_id,
        username=anonymized_username(user_id, display_name=display_name),
        member_since=row["created_at"],
        trade_count=total_trades,
        settled_trade_count=settled_trades,
        win_rate=win_rate(int(row["wins"] or 0), settled_trades),
        roi=roi(realized_pnl, total_cost),
        followers_count=int(row["followers_count"] or 0),
        following_count=int(row["following_count"] or 0),
    )


async def get_public_trader_profile(
    db: AsyncSession,
    requested_name: str,
) -> PublicTraderProfile | None:
    """Resolve an anonymized or explicit public display name without exposing IDs."""
    requested = requested_name.strip().casefold()
    if not requested:
        return None

    result = await db.execute(text(PUBLIC_TRADER_PROFILE_SQL))
    matches: list[PublicTraderProfile] = []
    for row in result.mappings().all():
        profile = _profile_from_row(row)
        if profile.username.casefold() == requested:
            matches.append(profile)
    # Duplicate display names are ambiguous; do not guess or disclose either user.
    if len(matches) != 1:
        return None
    return matches[0]
