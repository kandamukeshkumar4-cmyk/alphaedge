from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.data.fifa.loaders import load_wc2026_fixtures
from app.db.session import get_db
from app.ml.wc2026_model import predict_match
from app.schemas.wc2026 import WC2026Match, WC2026ScheduleResponse, WC2026SeedResponse
from app.services.price_snapshot_seed import latest_seed_implied_yes
from app.services.wc2026_seeder import seed_wc2026_markets

router = APIRouter(prefix="/api/v1/wc2026", tags=["wc2026"])
admin_router = APIRouter(prefix="/api/v1/admin/wc2026", tags=["admin-wc2026"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_probs(p_home: float, p_draw: float, p_away: float) -> tuple[float, float, float]:
    total = p_home + p_draw + p_away
    if total <= 0:
        return (1 / 3, 1 / 3, 1 / 3)
    probs = [p_home / total, p_draw / total, p_away / total]
    rounded = [round(p, 4) for p in probs]
    drift = round(1.0 - sum(rounded), 4)
    if drift:
        adjust_idx = max(range(3), key=lambda i: rounded[i])
        rounded[adjust_idx] = round(rounded[adjust_idx] + drift, 4)
    return rounded[0], rounded[1], rounded[2]


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _slug_triplet(row) -> tuple[str, str, str]:
    fixture_id = int(row["id"])
    home_code = str(row["home_team_code"]).upper()
    away_code = str(row["away_team_code"]).upper()
    return (
        f"wc2026-{fixture_id}-{home_code}win",
        f"wc2026-{fixture_id}-draw",
        f"wc2026-{fixture_id}-{away_code}win",
    )


async def _markets_for_fixture(db: AsyncSession, row) -> list[dict]:
    home_slug, draw_slug, away_slug = _slug_triplet(row)
    slugs = {
        "home_win": home_slug,
        "draw": draw_slug,
        "away_win": away_slug,
    }

    implied: dict[str, float | None] = {}
    for outcome, slug in slugs.items():
        implied[outcome] = await latest_seed_implied_yes(db, slug)

    if any(implied[outcome] is None for outcome in slugs):
        return []

    return [
        {"outcome": outcome, "slug": slug, "implied_yes": implied[outcome]}
        for outcome, slug in slugs.items()
    ]


@router.get("/schedule", response_model=WC2026ScheduleResponse)
async def get_wc2026_schedule(
    days: int = Query(default=14, ge=1, le=90),
    stage: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> WC2026ScheduleResponse:
    fixtures = load_wc2026_fixtures()
    now = _utc_now()
    window_end = now + timedelta(days=days)
    matches: list[WC2026Match] = []

    if fixtures is not None:
        for _, row in fixtures.iterrows():
            if _parse_bool(row.get("home_is_placeholder")) or _parse_bool(row.get("away_is_placeholder")):
                continue
            if stage == "group" and str(row.get("stage_name")) != "Group Stage":
                continue

            kickoff_at = row.get("kickoff_at")
            if kickoff_at is None or kickoff_at < now or kickoff_at > window_end:
                continue

            home_code = str(row["home_team_code"])
            away_code = str(row["away_team_code"])
            p_home, p_draw, p_away = _normalize_probs(*predict_match(home_code, away_code, neutral=True))
            markets = await _markets_for_fixture(db, row)

            matches.append(
                WC2026Match(
                    fixture_id=int(row["id"]),
                    home_team=str(row["home_team_name"]),
                    away_team=str(row["away_team_name"]),
                    kickoff_at=kickoff_at.to_pydatetime()
                    if hasattr(kickoff_at, "to_pydatetime")
                    else kickoff_at,
                    venue=str(row.get("venue_name") or row.get("city_name") or ""),
                    stage_name=str(row.get("stage_name") or ""),
                    p_home_win=p_home,
                    p_draw=p_draw,
                    p_away_win=p_away,
                    markets=markets,
                )
            )

        matches.sort(key=lambda m: m.kickoff_at)

    return WC2026ScheduleResponse(matches=matches, generated_at=now)


@admin_router.post("/seed", response_model=WC2026SeedResponse)
async def admin_seed_wc2026(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> WC2026SeedResponse:
    summary = await seed_wc2026_markets(db)
    await db.commit()
    return WC2026SeedResponse(**summary)
