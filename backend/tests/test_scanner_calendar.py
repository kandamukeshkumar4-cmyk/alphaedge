"""P3 — scanner market-calendar awareness (market_hours_only)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from app.db.models import Scanner
from app.services.market_service import MarketService
from app.services.scanner_compiler_service import compile_scanner_spec
from app.services.scanner_scheduler_service import calendar_allows_run, run_due_scanners
from app.services.screener_query_service import (
    has_active_markets_in_categories,
    is_active_market,
    market_hours_only_enabled,
)


def _spec(*, market_hours_only: bool, categories=None) -> dict:
    return {
        "name": "cal",
        "universe": {"categories": categories or ["nba", "sports"], "minimum_volume": 0},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": market_hours_only,
            "interval_minutes": 30,
        },
        "steps": [{"type": "WHALE_FLOW"}],
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
        "limit": 10,
    }


def test_compiler_parses_market_hours_only():
    spec = compile_scanner_spec(
        "Scan nba sports markets every 30 minutes for whale flow market hours only"
    )
    assert spec["schedule"]["market_hours_only"] is True
    assert market_hours_only_enabled(spec) is True


def test_is_active_market_requires_open_and_volume():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)

    class _M:
        def __init__(self, lock_at, volume):
            self.lock_at = lock_at
            self.volume = volume

    assert is_active_market(_M(now + timedelta(hours=2), 100), now) is True
    assert is_active_market(_M(now - timedelta(hours=1), 100), now) is False  # closed
    assert is_active_market(_M(now + timedelta(hours=2), 0), now) is False  # no volume
    assert is_active_market(_M(None, 100), now) is False


@pytest.mark.asyncio
async def test_has_active_markets_in_categories(db_session):
    now = datetime.now(UTC)
    svc = MarketService(db_session)
    await svc.create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers beat the Celtics?",
        lock_at=now + timedelta(hours=3),
        category="NBA",
        volume=50000,
    )
    await db_session.flush()
    assert await has_active_markets_in_categories(db_session, ["nba"], now=now) is True
    assert await has_active_markets_in_categories(db_session, ["crypto"], now=now) is False


@pytest.mark.asyncio
async def test_calendar_allows_run_skips_when_no_active(db_session):
    now = datetime.now(UTC)
    svc = MarketService(db_session)
    # Locked / zero volume — not active
    await svc.create_market(
        slug="nba-closed",
        title="Closed NBA",
        question="done?",
        lock_at=now - timedelta(hours=1),
        category="NBA",
        volume=0,
    )
    await db_session.flush()
    spec = _spec(market_hours_only=True, categories=["nba"])
    assert await calendar_allows_run(db_session, spec, now=now) is False
    # Without flag, always allowed
    spec_off = _spec(market_hours_only=False, categories=["nba"])
    assert await calendar_allows_run(db_session, spec_off, now=now) is True


@pytest.mark.asyncio
async def test_run_due_scanners_skips_market_hours_only(db_session, monkeypatch):
    now = datetime.now(UTC)
    ran_ids = []

    async def _fake_run(db, scanner, **kwargs):
        ran_ids.append(scanner.id)
        return None

    monkeypatch.setattr(
        "app.services.scanner_scheduler_service.run_scanner", _fake_run
    )

    # Active market in nba
    svc = MarketService(db_session)
    await svc.create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers beat the Celtics?",
        lock_at=now + timedelta(hours=2),
        category="NBA",
        volume=25000,
    )

    allow = Scanner(
        name="allow",
        owner="t",
        spec=_spec(market_hours_only=True, categories=["nba"]),
        status="active",
        cooldown_minutes=0,
    )
    skip = Scanner(
        name="skip",
        owner="t",
        spec=_spec(market_hours_only=True, categories=["crypto"]),
        status="active",
        cooldown_minutes=0,
    )
    always = Scanner(
        name="always",
        owner="t",
        spec=_spec(market_hours_only=False, categories=["crypto"]),
        status="active",
        cooldown_minutes=0,
    )
    db_session.add_all([allow, skip, always])
    await db_session.flush()

    result = await run_due_scanners(db_session, now=now)
    assert result["due"] == 3
    assert result["skipped_calendar"] == 1
    assert result["ran"] == 2
    assert allow.id in ran_ids
    assert always.id in ran_ids
    assert skip.id not in ran_ids
