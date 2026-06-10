"""Seed WC2026 group-stage binary outcome markets from fixtures + model prices."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.fifa.loaders import load_wc2026_fixtures, parse_bool
from app.db.models import Market
from app.ml.wc2026_model import predict_match
from app.services.market_service import MarketService
from app.services.price_snapshot_seed import seed_price_snapshots

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "fifa"


def _group_letter(row) -> str:
    letter = str(row.get("home_group_letter") or row.get("match_label", "")).strip()
    if letter and len(letter) == 1:
        return letter
    label = str(row.get("match_label", ""))
    if label.startswith("Group ") and len(label) >= 7:
        return label.split()[-1]
    return letter or "?"


def _market_specs_for_fixture(row, p_home: float, p_draw: float, p_away: float) -> list[dict]:
    fixture_id = int(row["id"])
    home_name = str(row["home_team_name"])
    away_name = str(row["away_team_name"])
    home_code = str(row["home_team_code"]).upper()
    away_code = str(row["away_team_code"]).upper()
    group = _group_letter(row)

    return [
        {
            "slug": f"wc2026-{fixture_id}-{home_code}win",
            "title": f"{home_name} to beat {away_name} — WC2026 Group {group}",
            "question": f"Will {home_name} beat {away_name} in regulation?",
            "price": p_home,
            "outcome": "home_win",
        },
        {
            "slug": f"wc2026-{fixture_id}-draw",
            "title": f"{home_name} vs {away_name} Draw — WC2026 Group {group}",
            "question": f"Will {home_name} vs {away_name} end in a draw?",
            "price": p_draw,
            "outcome": "draw",
        },
        {
            "slug": f"wc2026-{fixture_id}-{away_code}win",
            "title": f"{away_name} to beat {home_name} — WC2026 Group {group}",
            "question": f"Will {away_name} beat {home_name} in regulation?",
            "price": p_away,
            "outcome": "away_win",
        },
    ]


async def seed_wc2026_markets(
    session: AsyncSession,
    *,
    data_dir: Path = DATA_DIR,
) -> dict[str, int]:
    fixtures = load_wc2026_fixtures(data_dir)
    if fixtures is None:
        return {"created": 0, "skipped": 0, "fixtures": 0}

    market_service = MarketService(session)
    created = 0
    skipped = 0
    eligible = 0

    for _, row in fixtures.iterrows():
        if parse_bool(row.get("home_is_placeholder")) or parse_bool(row.get("away_is_placeholder")):
            continue
        eligible += 1

        home_code = str(row["home_team_code"])
        away_code = str(row["away_team_code"])
        p_home, p_draw, p_away = predict_match(home_code, away_code, neutral=True)

        for spec in _market_specs_for_fixture(row, p_home, p_draw, p_away):
            existing = await session.scalar(select(Market).where(Market.slug == spec["slug"]))
            if existing is not None:
                skipped += 1
                continue

            kickoff_at = row["kickoff_at"]
            lock_at = kickoff_at + timedelta(hours=2) if kickoff_at is not None else None
            venue = str(row.get("venue_name") or row.get("city_name") or "")

            await market_service.create_market(
                slug=spec["slug"],
                title=spec["title"],
                question=spec["question"],
                lock_at=lock_at,
                category="sports",
                icon="⚽",
                volume=0,
                traders=0,
                market_count=3,
                description=(
                    f"FIFA World Cup 2026 — {row.get('stage_name', 'Group Stage')} at {venue}. "
                    "Paper-trading simulation only."
                ),
                resolution="Resolves YES if the named outcome occurs in regulation time.",
                tournament_tag="wc2026",
            )
            await seed_price_snapshots(
                session,
                spec["slug"],
                end_price=spec["price"],
                n_points=90,
                step_sec=3600,
            )
            created += 1

    await session.flush()
    return {"created": created, "skipped": skipped, "fixtures": eligible}
