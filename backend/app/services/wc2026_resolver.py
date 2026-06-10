"""Poll football-data.org for finished WC2026 scores and settle outcome markets."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.data.fifa.loaders import load_wc2026_fixtures, parse_bool
from app.db.models import Market, MarketStatus
from app.services.settlement_service import settle_market

logger = logging.getLogger(__name__)

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# football-data.org TLA → fixture CSV team_code
FOOTBALL_DATA_TLA_MAP: dict[str, str] = {
    "ZAF": "RSA",
}


@dataclass(frozen=True)
class MatchResult:
    fixture_id: int
    home_goals: int
    away_goals: int


def _normalize_tla(tla: str) -> str:
    code = tla.strip().upper()
    return FOOTBALL_DATA_TLA_MAP.get(code, code)


def _fixture_id_for_teams(fixtures_df, home_tla: str, away_tla: str) -> int | None:
    home_tla = _normalize_tla(home_tla)
    away_tla = _normalize_tla(away_tla)
    for _, row in fixtures_df.iterrows():
        if parse_bool(row.get("home_is_placeholder")) or parse_bool(row.get("away_is_placeholder")):
            continue
        hc = str(row["home_team_code"]).upper()
        ac = str(row["away_team_code"]).upper()
        if hc == home_tla and ac == away_tla:
            return int(row["id"])
    return None


def _slug_triplet(fixture_id: int, home_code: str, away_code: str) -> dict[str, str]:
    home_code = home_code.upper()
    away_code = away_code.upper()
    return {
        "home_win": f"wc2026-{fixture_id}-{home_code}win",
        "draw": f"wc2026-{fixture_id}-draw",
        "away_win": f"wc2026-{fixture_id}-{away_code}win",
    }


def _winning_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home_win"
    if home_goals == away_goals:
        return "draw"
    return "away_win"


async def fetch_wc2026_results(session: httpx.AsyncClient) -> list[MatchResult]:
    """Poll football-data.org for finished WC matches.

    Uses ``/v4/competitions/WC/matches?status=FINISHED``.
    """
    settings = get_settings()
    if not settings.football_data_api_key:
        logger.info("FOOTBALL_DATA_API_KEY unset — skipping live score poll")
        return []

    fixtures = load_wc2026_fixtures()
    if fixtures is None:
        return []

    try:
        response = await session.get(
            f"{FOOTBALL_DATA_BASE}/competitions/WC/matches",
            params={"status": "FINISHED"},
            headers={"X-Auth-Token": settings.football_data_api_key},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "football-data.org returned HTTP %s — skipping resolution poll",
            exc.response.status_code,
        )
        return []
    except httpx.RequestError as exc:
        logger.warning("football-data.org request error: %s — skipping resolution poll", exc)
        return []

    results: list[MatchResult] = []
    for match in response.json().get("matches", []):
        if match.get("status") != "FINISHED":
            continue

        home_tla = str(match.get("homeTeam", {}).get("tla") or "").strip()
        away_tla = str(match.get("awayTeam", {}).get("tla") or "").strip()
        if not home_tla or not away_tla:
            continue

        fixture_id = _fixture_id_for_teams(fixtures, home_tla, away_tla)
        if fixture_id is None:
            continue

        full_time = match.get("score", {}).get("fullTime", {})
        home_goals = full_time.get("home")
        away_goals = full_time.get("away")
        if home_goals is None or away_goals is None:
            continue

        results.append(
            MatchResult(
                fixture_id=fixture_id,
                home_goals=int(home_goals),
                away_goals=int(away_goals),
            )
        )

    return results


async def resolve_finished_wc2026_markets(db: AsyncSession) -> dict[str, int]:
    """Settle WC2026 outcome markets for each finished match from the poller."""
    fixtures = load_wc2026_fixtures()
    if fixtures is None:
        return {"resolved": 0, "skipped": 0}

    fixture_rows = {int(row["id"]): row for _, row in fixtures.iterrows()}

    async with httpx.AsyncClient() as client:
        match_results = await fetch_wc2026_results(client)

    resolved = 0
    skipped = 0

    for result in match_results:
        row = fixture_rows.get(result.fixture_id)
        if row is None:
            skipped += 3
            continue

        home_code = str(row["home_team_code"])
        away_code = str(row["away_team_code"])
        winner = _winning_outcome(result.home_goals, result.away_goals)
        slugs = _slug_triplet(result.fixture_id, home_code, away_code)

        for outcome, slug in slugs.items():
            market = await db.scalar(select(Market).where(Market.slug == slug))
            if market is None:
                skipped += 1
                continue
            if market.status == MarketStatus.RESOLVED:
                skipped += 1
                continue

            winning_side = "YES" if outcome == winner else "NO"
            await settle_market(db, slug, winning_side)
            resolved += 1

    await db.flush()
    return {"resolved": resolved, "skipped": skipped}


async def wc2026_admin_status(db: AsyncSession) -> dict[str, int]:
    """Aggregate fixture seeding and resolution counts for admin status."""
    fixtures = load_wc2026_fixtures()
    if fixtures is None:
        return {"total_fixtures": 0, "seeded": 0, "resolved": 0, "pending": 0}

    eligible_ids: list[int] = []
    for _, row in fixtures.iterrows():
        if parse_bool(row.get("home_is_placeholder")) or parse_bool(row.get("away_is_placeholder")):
            continue
        eligible_ids.append(int(row["id"]))

    total_fixtures = len(eligible_ids)
    if total_fixtures == 0:
        return {"total_fixtures": 0, "seeded": 0, "resolved": 0, "pending": 0}

    slug_prefixes = [f"wc2026-{fid}-" for fid in eligible_ids]
    markets = (
        await db.scalars(select(Market).where(Market.tournament_tag == "wc2026"))
    ).all()

    relevant = [m for m in markets if any(m.slug.startswith(p) for p in slug_prefixes)]
    seeded = len(relevant)
    resolved = sum(1 for m in relevant if m.status == MarketStatus.RESOLVED)

    resolved_fixture_ids: set[int] = set()
    for fid in eligible_ids:
        prefix = f"wc2026-{fid}-"
        fixture_markets = [m for m in relevant if m.slug.startswith(prefix)]
        if len(fixture_markets) == 3 and all(m.status == MarketStatus.RESOLVED for m in fixture_markets):
            resolved_fixture_ids.add(fid)

    pending = total_fixtures - len(resolved_fixture_ids)

    return {
        "total_fixtures": total_fixtures,
        "seeded": seeded,
        "resolved": resolved,
        "pending": pending,
    }
