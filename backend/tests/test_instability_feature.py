"""T13 — instability forecasting features: flag-gated, eligible markets only."""
from __future__ import annotations

from datetime import UTC, datetime

from app.signals.event_taxonomy import EventCategory
from app.signals.instability import (
    TaggedItem,
    build_instability_features,
    is_instability_feature_market,
)

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
ITEMS = [
    TaggedItem(region="MidEast", category=EventCategory.MILITARY, ts=NOW),
    TaggedItem(region="MidEast", category=EventCategory.DIPLOMACY, ts=NOW),
]


def test_flag_off_returns_empty():
    feats = build_instability_features(
        market_category="Politics", region_score=60.0, items=ITEMS, enabled=False
    )
    assert feats == {}


def test_eligible_market_gets_features_when_on():
    feats = build_instability_features(
        market_category="Politics", region_score=60.0, items=ITEMS, enabled=True
    )
    assert feats["instability_score"] == 60.0
    assert feats["event_category_counts"]["military"] == 1


def test_geopolitics_and_economics_eligible():
    assert is_instability_feature_market("Geopolitics") is True
    assert is_instability_feature_market("Economics") is True
    assert is_instability_feature_market("Politics") is True


def test_nba_and_sports_never_get_features():
    for cat in ("NBA", "Sports", "Crypto", "Culture", None):
        assert is_instability_feature_market(cat) is False
        feats = build_instability_features(
            market_category=cat, region_score=90.0, items=ITEMS, enabled=True
        )
        assert feats == {}  # NBA/sports NEVER receive instability features
