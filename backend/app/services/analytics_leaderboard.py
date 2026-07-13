"""Leaderboard ranking math over settled paper trades (Loop V15 B1).

Pure helpers are unit-tested without the DB. Aggregation SQL mirrors the
existing endpoint's settlement formula (shares×1 − cost on win, −cost on loss)
so completed work stays additive — do not rebuild a divergent PnL path.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

SortKey = Literal["realized_pnl", "roi", "win_rate"]

LEADERBOARD_TTL_SEC = 5.0
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class LeaderboardRow:
    user_id: UUID
    display_name: str | None
    realized_pnl: float
    total_cost: float
    total_trades: int
    wins: int
    settled_trades: int


@dataclass(frozen=True)
class RankedEntry:
    rank: int
    username: str
    realized_pnl: float
    total_trades: int
    win_rate: float
    roi: float


def win_rate(wins: int, settled_trades: int) -> float:
    if settled_trades <= 0:
        return 0.0
    return round(wins / settled_trades, 4)


def roi(realized_pnl: float, total_cost: float) -> float:
    """ROI = realized PnL / capital risked. Zero cost → 0 (no divide-by-zero)."""
    if total_cost <= 0:
        return 0.0
    return round(realized_pnl / total_cost, 4)


def anonymized_username(
    user_id: UUID,
    *,
    display_name: str | None = None,
) -> str:
    """Prefer explicit display_name; otherwise a stable anonymized label.

    Never emits email or email-local parts (public leaderboard).
    """
    if display_name and display_name.strip():
        return display_name.strip()[:32]
    digest = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:6]
    return f"Trader-{digest}"


def sort_key_value(row: LeaderboardRow, sort: SortKey) -> float:
    if sort == "roi":
        return roi(row.realized_pnl, row.total_cost)
    if sort == "win_rate":
        return win_rate(row.wins, row.settled_trades)
    return row.realized_pnl


def rank_rows(
    rows: list[LeaderboardRow],
    *,
    sort: SortKey = "realized_pnl",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[RankedEntry], int]:
    """Rank users with settled trades. Returns (page, total_eligible).

    Primary metric DESC; ties broken by user_id ASC for a stable total order
    (unique ranks). Users with zero settled trades are excluded.
    """
    eligible = [r for r in rows if r.settled_trades > 0]
    eligible.sort(
        key=lambda r: (-sort_key_value(r, sort), str(r.user_id)),
    )
    total = len(eligible)
    page_rows = eligible[offset : offset + limit]
    entries: list[RankedEntry] = []
    for i, row in enumerate(page_rows):
        rank = offset + i + 1
        entries.append(
            RankedEntry(
                rank=rank,
                username=anonymized_username(
                    row.user_id,
                    display_name=row.display_name,
                ),
                realized_pnl=round(row.realized_pnl, 4),
                total_trades=row.total_trades,
                win_rate=win_rate(row.wins, row.settled_trades),
                roi=roi(row.realized_pnl, row.total_cost),
            )
        )
    return entries, total


# Aggregation used by the API — kept as a constant so the router stays thin.
LEADERBOARD_AGG_SQL = """
SELECT
    po.user_id,
    u.display_name,
    SUM(
        CASE
            WHEN po.settled IS TRUE
                 AND UPPER(po.outcome) = COALESCE(mr.outcome, '')
            THEN po.shares * 1.0 - po.cost
            WHEN po.settled IS TRUE THEN 0.0 - po.cost
            ELSE 0.0
        END
    ) AS realized_pnl,
    SUM(
        CASE WHEN po.settled IS TRUE THEN po.cost ELSE 0.0 END
    ) AS total_cost,
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
GROUP BY po.user_id, u.display_name
"""
