"""T13 — event taxonomy classifier + region extraction (clean-room)."""
from __future__ import annotations

import pytest

from app.signals.event_taxonomy import (
    EventCategory,
    category_severity,
    classify_event,
    extract_region,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Missile strikes escalate the war", EventCategory.MILITARY),
        ("Mass protest and riot in the capital", EventCategory.UNREST),
        ("Major ransomware breach hits infrastructure", EventCategory.CYBER),
        ("Supreme court verdict on the lawsuit", EventCategory.LEGAL),
        ("Presidential election ballot count", EventCategory.ELECTIONS),
        ("Hurricane and flood devastate coast", EventCategory.CLIMATE),
        ("Fed inflation and interest rate move", EventCategory.ECONOMY),
        ("Pandemic vaccine rollout", EventCategory.HEALTH),
        ("random cooking recipe", EventCategory.OTHER),
    ],
)
def test_classify_event(text, expected):
    assert classify_event(text) == expected


def test_classify_never_crashes_on_empty():
    assert classify_event("") == EventCategory.OTHER
    assert classify_event(None) == EventCategory.OTHER  # type: ignore[arg-type]


def test_higher_severity_wins_on_multi_match():
    # both military and elections keywords present -> military (higher severity) wins
    assert classify_event("war breaks out during the election") == EventCategory.MILITARY


@pytest.mark.parametrize(
    "text,region",
    [
        ("White House statement from Washington", "US"),
        ("Brussels and Germany respond", "EU"),
        ("Israel and Iran tensions", "MidEast"),
        ("China and Taiwan standoff", "Asia"),
        ("Russia Ukraine front line", "Russia"),
        ("nothing geographic here", "Global"),
    ],
)
def test_extract_region(text, region):
    assert extract_region(text) == region


def test_severity_ordering():
    assert category_severity(EventCategory.MILITARY) > category_severity(EventCategory.TECH)
    assert 0.0 <= category_severity(EventCategory.OTHER) <= 1.0
