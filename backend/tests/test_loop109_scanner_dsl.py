"""Loop109 — two new scanner DSL capabilities.

CROSS_VENUE_DIVERGENCE (same event priced differently on Polymarket vs Kalshi)
and CLOSING_SOON (time-to-lock filter) must be first-class in the compiler
whitelist, range-validated, executable on the real run path, and seeded as
public starters — without regressing the eight Loop107 starters.

Research-only: no orders, no RiskService / OrderBookService, no LLM calls.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Scanner, VenueGap
from app.services.market_service import MarketService
from app.services.scanner_compiler_service import (
    is_valid_compiled_spec,
    validate_spec,
)
from app.services.scanner_executor_service import run_scanner
from app.services.scanner_seed_service import STARTER_SCANNERS, seed_starter_scanners

LOOP107_SEED_NAMES = {
    "Big Mover Radar",
    "Whale Flow Watch",
    "Model Edge Radar",
    "High-Volume Momentum",
    "News Pulse Confirmed",
    "Triple Confirmation",
    "NBA Sharp Money",
    "Election Edge Watch",
}
NEW_SEED_NAMES = {"Cross-Venue Divergence", "Closing Soon, High Volume"}


def _spec(steps: list[dict], *, interval_minutes: int = 60) -> dict:
    return {
        "name": "loop109 probe",
        "universe": {"categories": ["sports"], "minimum_volume": 0},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": False,
            "interval_minutes": interval_minutes,
        },
        "steps": steps,
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": 240},
        "limit": 20,
        "notes": [],
    }


async def _scanner(db, steps: list[dict], name: str) -> Scanner:
    scanner = Scanner(
        name=name,
        description="loop109 probe",
        owner=None,
        spec=_spec(steps),
        version=1,
        status="active",
        is_public=False,
        is_featured=False,
        cooldown_minutes=240,
    )
    db.add(scanner)
    await db.flush()
    return scanner


# ---------------------------------------------------------------- compiler


def test_cross_venue_step_compiles_and_validates_params():
    """CROSS_VENUE_DIVERGENCE is whitelisted; in-range min_gap passes."""
    spec = _spec([{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": 0.05}])
    assert is_valid_compiled_spec(spec)
    # It scores a mispricing, so it satisfies the "signal step" requirement.
    assert validate_spec(spec) == []

    for gap in (0.01, 0.05, 0.2, 0.5):
        assert is_valid_compiled_spec(
            _spec([{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": gap}])
        ), gap
    # Omitted param falls back to the documented default.
    assert is_valid_compiled_spec(_spec([{"type": "CROSS_VENUE_DIVERGENCE"}]))
    # A very tight gap is legal but warned about.
    assert (
        "cross-venue min_gap below 0.02 will surface noise"
        in validate_spec(_spec([{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": 0.015}]))
    )


def test_cross_venue_rejects_out_of_range_min_gap():
    for bad in (0.0, 0.009, 0.51, 1.0, -0.1, "wide", "", None, True, float("nan")):
        assert not is_valid_compiled_spec(
            _spec([{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": bad}])
        ), bad
    # Numeric strings stay accepted, matching the existing interval_minutes
    # check (and scanner_heal_service's numeric-string coercion).
    assert is_valid_compiled_spec(
        _spec([{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": "0.05"}])
    )


def test_closing_soon_rejects_out_of_range_hours():
    for good in (1, 24, 168):
        assert is_valid_compiled_spec(
            _spec([{"type": "CLOSING_SOON", "within_hours": good}])
        ), good
    for bad in (0, -1, 169, 1000, 1.5, "soon", "", None, True):
        assert not is_valid_compiled_spec(
            _spec([{"type": "CLOSING_SOON", "within_hours": bad}])
        ), bad
    # Numeric strings stay accepted (same convention as interval_minutes).
    assert is_valid_compiled_spec(
        _spec([{"type": "CLOSING_SOON", "within_hours": "24"}])
    )

    # CLOSING_SOON is a filter, not a signal: alone it warns.
    assert "no signal steps" in validate_spec(
        _spec([{"type": "CLOSING_SOON", "within_hours": 24}])
    )
    # Duplicates and windows shorter than the scan interval are called out.
    dup = _spec(
        [
            {"type": "CLOSING_SOON", "within_hours": 24},
            {"type": "CLOSING_SOON", "within_hours": 1},
            {"type": "MODEL_EDGE"},
        ],
        interval_minutes=120,
    )
    warnings = validate_spec(dup)
    assert "duplicate CLOSING_SOON step" in warnings
    assert "closing window shorter than scan interval" in warnings


# ---------------------------------------------------------------- executor


@pytest.mark.asyncio
async def test_cross_venue_executor_scores_gap_and_skips_unmirrored(db_session):
    """Wide gap kept + annotated; narrow gap dropped; unmirrored skipped."""
    svc = MarketService(db_session)
    now = datetime.now(UTC)
    for slug, title, volume in [
        ("nba-2025-01-15-lal-bos", "Lakers vs Celtics", 50000),
        ("nba-2025-01-16-nyk-mia", "Knicks vs Heat", 40000),
        ("nba-2025-01-17-gsw-den", "Warriors vs Nuggets", 30000),
    ]:
        await svc.create_market(
            slug=slug,
            title=title,
            question=f"Will {title.split(' vs ')[0]} win?",
            lock_at=now + timedelta(hours=6),
            category="Sports",
            volume=volume,
        )
    # Mirror pairs come from the existing venue_gaps table. The third market
    # deliberately has no mirror row at all.
    db_session.add_all(
        [
            VenueGap(
                pm_slug="nba-2025-01-15-lal-bos",
                ks_slug="KX-LAL-BOS",
                pm_implied=Decimal("0.6000"),
                ks_implied=Decimal("0.5200"),
                gap=Decimal("0.0800"),
                abs_gap=Decimal("0.0800"),
                match_confidence=0.9,
                stale=False,
                captured_at=now,
            ),
            VenueGap(
                pm_slug="nba-2025-01-16-nyk-mia",
                ks_slug="KX-NYK-MIA",
                pm_implied=Decimal("0.4100"),
                ks_implied=Decimal("0.4000"),
                gap=Decimal("0.0100"),
                abs_gap=Decimal("0.0100"),
                match_confidence=0.9,
                stale=False,
                captured_at=now,
            ),
        ]
    )
    await db_session.flush()

    scanner = await _scanner(
        db_session,
        [{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": 0.05}],
        "loop109 cross venue",
    )
    run = await run_scanner(db_session, scanner)

    assert run.error is None
    assert run.status == "completed"
    slugs = [c["market_slug"] for c in run.result["candidates"]]
    assert slugs == ["nba-2025-01-15-lal-bos"]

    read = run.result["candidates"][0]["reads"]["CROSS_VENUE_DIVERGENCE"]
    assert read["pm_implied"] == pytest.approx(0.60)
    assert read["ks_implied"] == pytest.approx(0.52)
    assert read["abs_gap"] == pytest.approx(0.08)
    assert read["min_gap"] == pytest.approx(0.05)
    assert read["ks_slug"] == "KX-LAL-BOS"
    assert read["stale"] is False
    # Universe counted all three; only the mirrored, wide-gap market survived.
    assert run.result["counts"]["universe"] == 3
    assert run.result["counts"]["candidates"] == 1


@pytest.mark.asyncio
async def test_closing_soon_filters_by_lock_window_and_skips_unlocked(db_session):
    """Only still-open markets locking inside the window survive."""
    svc = MarketService(db_session)
    now = datetime.now(UTC)
    await svc.create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=now + timedelta(hours=2),
        category="Sports",
        volume=50000,
    )
    await svc.create_market(
        slug="nba-2025-02-20-nyk-mia",
        title="Knicks vs Heat",
        question="Will the Knicks win?",
        lock_at=now + timedelta(hours=100),
        category="Sports",
        volume=40000,
    )
    await svc.create_market(
        slug="nba-undated-gsw-den",
        title="Warriors vs Nuggets",
        question="Will the Warriors win?",
        lock_at=None,
        category="Sports",
        volume=30000,
    )
    await db_session.flush()

    scanner = await _scanner(
        db_session,
        [{"type": "CLOSING_SOON", "within_hours": 24}],
        "loop109 closing soon",
    )
    run = await run_scanner(db_session, scanner)

    assert run.error is None
    slugs = [c["market_slug"] for c in run.result["candidates"]]
    assert slugs == ["nba-2025-01-15-lal-bos"]
    read = run.result["candidates"][0]["reads"]["CLOSING_SOON"]
    assert read["within_hours"] == 24
    assert 0 < read["hours_to_lock"] <= 24
    assert read["lock_at"]
    assert run.result["counts"]["universe"] == 3

    # A 1-hour window keeps nothing (the only in-window market locks in 2h).
    tight = await _scanner(
        db_session,
        [{"type": "CLOSING_SOON", "within_hours": 1}],
        "loop109 closing soon tight",
    )
    tight_run = await run_scanner(db_session, tight)
    assert tight_run.error is None
    assert tight_run.result["candidates"] == []


# ---------------------------------------------------------------- seeds


@pytest.mark.asyncio
async def test_new_seeds_compile_and_are_idempotent(db_session):
    by_name = {entry["name"]: entry for entry in STARTER_SCANNERS}
    assert NEW_SEED_NAMES <= set(by_name)

    for name in NEW_SEED_NAMES:
        entry = by_name[name]
        assert is_valid_compiled_spec(entry["spec"]), name
        assert validate_spec(entry["spec"]) == [], name
        assert entry["description"]
        assert entry.get("is_featured") is False, name

    cross = by_name["Cross-Venue Divergence"]["spec"]["steps"]
    assert cross == [{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": 0.05}]
    closing = by_name["Closing Soon, High Volume"]["spec"]
    assert closing["steps"][0] == {"type": "CLOSING_SOON", "within_hours": 24}
    assert closing["universe"]["minimum_volume"] == 25000

    first = await seed_starter_scanners(db_session)
    second = await seed_starter_scanners(db_session)
    assert first == len(STARTER_SCANNERS)
    assert second == 0

    rows = (
        await db_session.scalars(
            select(Scanner).where(Scanner.name.in_(sorted(NEW_SEED_NAMES)))
        )
    ).all()
    assert {r.name for r in rows} == NEW_SEED_NAMES
    for row in rows:
        assert row.owner is None
        assert row.is_public is True
        assert row.is_featured is False


@pytest.mark.asyncio
async def test_existing_seeded_scanners_still_compile(db_session):
    """Regression: the eight Loop107 starters are untouched and still valid."""
    by_name = {entry["name"]: entry for entry in STARTER_SCANNERS}
    assert LOOP107_SEED_NAMES <= set(by_name)
    for name in sorted(LOOP107_SEED_NAMES):
        entry = by_name[name]
        assert is_valid_compiled_spec(entry["spec"]), name
        assert validate_spec(entry["spec"]) == [], name
        # Loop115 made featuring selective (flagship four only), so the old
        # "every seed is featured" assert is stale by design — the field only
        # has to remain a bool.
        assert isinstance(entry.get("is_featured", True), bool), name

    await seed_starter_scanners(db_session)
    rows = (
        await db_session.scalars(
            select(Scanner).where(Scanner.name.in_(sorted(LOOP107_SEED_NAMES)))
        )
    ).all()
    assert {r.name for r in rows} == LOOP107_SEED_NAMES
    for row in rows:
        assert isinstance(row.is_featured, bool)
        assert is_valid_compiled_spec(row.spec)
