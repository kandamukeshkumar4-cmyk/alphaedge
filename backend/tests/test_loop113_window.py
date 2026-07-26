"""Tests for loop113 venue match window and comparison capping."""

import pytest
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.models import Market, MarketStatus, VenueMarketMatch
from app.services.venue_match_service import VenueMatchService
from sqlalchemy import select

@pytest.mark.asyncio
async def test_catalog_limit_config_is_honored(db_session, monkeypatch):
    """The configured VENUE_MATCH_CATALOG_LIMIT dictates how many open markets are scanned."""
    settings = get_settings()
    monkeypatch.setattr(settings, "venue_match_catalog_limit", 15)
    
    now = datetime.now(UTC)
    for i in range(20):
        db_session.add(
            Market(
                source="polymarket",
                slug=f"pm-market-{i}",
                status=MarketStatus.OPEN,
                lock_at=now + timedelta(days=i),
                volume=100.0 * (20 - i),
                title=f"PM Market {i}",
                question=f"PM Market {i}?"
            )
        )
        db_session.add(
            Market(
                source="kalshi",
                slug=f"ks-market-{i}",
                status=MarketStatus.OPEN,
                lock_at=now + timedelta(days=i),
                volume=100.0,
                title=f"KS Market {i}",
                question=f"KS Market {i}?"
            )
        )
    await db_session.commit()
    
    service = VenueMatchService(db_session)
    await service.match_open_catalog()
    
    assert service.last_scan_stats["pm_scanned"] == 15
    assert service.last_scan_stats["ks_scanned"] == 15

@pytest.mark.asyncio
async def test_pairs_beyond_200_are_scanned_with_default_500(db_session, monkeypatch):
    """The default catalog limit of 500 scans markets that a 200 limit would miss, prioritizing by volume for PM."""
    settings = get_settings()
    monkeypatch.setattr(settings, "venue_match_catalog_limit", 500)
    
    now = datetime.now(UTC)
    db_session.add(
        Market(
            source="polymarket",
            slug="pm-target-ben-gvir",
            status=MarketStatus.OPEN,
            lock_at=now + timedelta(days=250),
            volume=999999.0,
            title="Will Itamar Ben Gvir be the next Prime Minister of Israel?",
            question="Will Itamar Ben Gvir be the next Prime Minister of Israel?"
        )
    )
    for i in range(400):
        db_session.add(
            Market(
                source="polymarket",
                slug=f"pm-filler-{i}",
                status=MarketStatus.OPEN,
                lock_at=now + timedelta(days=i),
                volume=1.0,
                title=f"PM Filler {i}",
                question=f"PM Filler {i}?"
            )
        )
        
    db_session.add(
        Market(
            source="kalshi",
            slug="ks-target-ben-gvir",
            status=MarketStatus.OPEN,
            lock_at=now + timedelta(days=250),
            volume=1.0,
            title="Who will succeed Netanyahu as Prime Minister of Israel?: Itamar Ben-Gvir",
            question="Who will succeed Netanyahu as Prime Minister of Israel?: Itamar Ben-Gvir"
        )
    )
    for i in range(300):
        db_session.add(
            Market(
                source="kalshi",
                slug=f"ks-filler-{i}",
                status=MarketStatus.OPEN,
                lock_at=now + timedelta(days=i),
                volume=1.0,
                title=f"KS Filler {i}",
                question=f"KS Filler {i}?"
            )
        )
    await db_session.commit()
    
    service = VenueMatchService(db_session)
    await service.match_open_catalog(max_pairs=5)
    
    assert service.last_scan_stats["pm_scanned"] <= 500
    assert service.last_scan_stats["ks_scanned"] <= 500
    
    matches = (await db_session.scalars(select(VenueMarketMatch))).all()
    assert any(m.pm_slug == "pm-target-ben-gvir" and m.ks_slug == "ks-target-ben-gvir" for m in matches)

@pytest.mark.asyncio
async def test_pair_comparison_cap_still_binds(db_session, monkeypatch):
    """The max_pairs cap bounds the O(pm x ks) title comparisons, not just accepted candidates."""
    settings = get_settings()
    monkeypatch.setattr(settings, "venue_match_catalog_limit", 100)
    
    now = datetime.now(UTC)
    for i in range(20):
        db_session.add(
            Market(
                source="polymarket",
                slug=f"pm-shared-{i}",
                status=MarketStatus.OPEN,
                lock_at=now + timedelta(days=i),
                volume=100.0,
                title="Shared token match candidate",
                question="Shared token match candidate"
            )
        )
        db_session.add(
            Market(
                source="kalshi",
                slug=f"ks-shared-{i}",
                status=MarketStatus.OPEN,
                lock_at=now + timedelta(days=i),
                volume=100.0,
                title="Shared token match candidate",
                question="Shared token match candidate"
            )
        )
    await db_session.commit()
    
    service = VenueMatchService(db_session)
    await service.match_open_catalog(max_pairs=5, min_confidence=0.9)
    
    assert service.last_scan_stats["pairs_scored"] == 5
