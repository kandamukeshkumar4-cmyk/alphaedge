"""Loop107 — public starter-scanner seed catalog.

Every seeded spec must pass the compiler's own whitelist/schema validation,
seeding must be idempotent, the catalog must be publicly listed, and at least
one starter must execute end-to-end on the real run path (research-only).
"""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.models import OddsSnapshot, Scanner
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.scanner_compiler_service import (
    is_valid_compiled_spec,
    validate_spec,
)
from app.services.scanner_executor_service import run_scanner
from app.services.scanner_seed_service import STARTER_SCANNERS, seed_starter_scanners

EXPECTED_NAMES = {entry["name"] for entry in STARTER_SCANNERS}

FLAGSHIP_FOUR = {
    "Big Mover Radar",
    "Whale Flow Watch",
    "Model Edge Radar",
    "Triple Confirmation",
}


def test_seeds_compile_through_the_real_compiler():
    """Each seed spec passes the compiler's schema check with zero warnings."""
    # Loop109 added two DSL starters (cross-venue divergence, closing soon).
    assert 5 <= len(STARTER_SCANNERS) <= 10
    for entry in STARTER_SCANNERS:
        spec = entry["spec"]
        assert is_valid_compiled_spec(spec), f"{entry['name']} rejected by compiler"
        assert validate_spec(spec) == [], f"{entry['name']} has compile warnings"
        assert entry["description"], f"{entry['name']} needs a description"


@pytest.mark.asyncio
async def test_seed_is_idempotent_on_second_run(db_session):
    first = await seed_starter_scanners(db_session)
    second = await seed_starter_scanners(db_session)
    assert first == len(STARTER_SCANNERS)
    assert second == 0

    rows = (await db_session.scalars(select(Scanner))).all()
    assert {row.name for row in rows} == EXPECTED_NAMES
    counts = (
        await db_session.execute(
            select(Scanner.name, func.count()).group_by(Scanner.name)
        )
    ).all()
    assert all(count == 1 for _, count in counts)


@pytest.mark.asyncio
async def test_seeded_scanners_are_public_and_listed(db_session):
    await seed_starter_scanners(db_session)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        response = await client.get("/api/v1/scanners/")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    by_name = {item["name"]: item for item in body}
    assert EXPECTED_NAMES <= set(by_name)
    for name in EXPECTED_NAMES:
        item = by_name[name]
        assert item["is_public"] is True
        assert item["owner"] is None
        assert item["description"]
        assert isinstance(item["spec"].get("steps"), list)


@pytest.mark.asyncio
async def test_featured_curation_is_flagship_four(db_session):
    """Exactly the flagship four starters are featured; the other six are not."""
    await seed_starter_scanners(db_session)

    rows = (await db_session.scalars(select(Scanner))).all()
    featured = {row.name for row in rows if row.is_featured}
    not_featured = {row.name for row in rows if not row.is_featured}

    assert featured == FLAGSHIP_FOUR
    assert not_featured == EXPECTED_NAMES - FLAGSHIP_FOUR
    assert len(featured) == 4
    assert len(not_featured) == 6


@pytest.mark.asyncio
async def test_seeded_scanner_runs_end_to_end(db_session):
    """One starter executes on the REAL run path against seeded test markets.

    Result rows may legitimately be empty; the run must simply not error.
    """
    svc = MarketService(db_session)
    now = datetime.now(UTC)
    for slug, title, p0, p1, volume in [
        ("nba-2025-01-15-lal-bos", "Lakers vs Celtics", 0.48, 0.55, 50000),
        ("nba-2025-01-16-nyk-mia", "Knicks vs Heat", 0.40, 0.45, 30000),
    ]:
        await svc.create_market(
            slug=slug,
            title=title,
            question=f"Will {title.split(' vs ')[0]} win?",
            lock_at=now + timedelta(hours=2),
            category="Sports",
            volume=volume,
        )
        db_session.add_all(
            [
                OddsSnapshot(
                    market_slug=slug,
                    implied_yes=p0,
                    captured_at=now - timedelta(days=1),
                ),
                OddsSnapshot(market_slug=slug, implied_yes=p1, captured_at=now),
            ]
        )
    await db_session.flush()

    await seed_starter_scanners(db_session)
    scanner = await db_session.scalar(
        select(Scanner).where(
            Scanner.name == "Big Mover Radar", Scanner.owner.is_(None)
        )
    )
    assert scanner is not None

    run = await run_scanner(db_session, scanner)
    assert run.error is None
    assert run.status in ("completed", "empty")
    assert isinstance(run.result, dict)
    assert "candidates" in run.result
