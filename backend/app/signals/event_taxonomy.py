"""Event taxonomy + classifier (T13).

CLEAN-ROOM: inspired only by the public description of worldmonitor's category idea;
no AGPL source was read or copied. The 15-category enum, keyword rules, severity
weights, and region patterns below are original.

Rule-based classifier first; an LLM refinement hook exists but the fallback (rules
only) is always sufficient — no LLM is required.
"""
from __future__ import annotations

import re
from enum import Enum


class EventCategory(str, Enum):
    MILITARY = "military"
    ELECTIONS = "elections"
    CYBER = "cyber"
    ENERGY = "energy"
    ECONOMY = "economy"
    LEGAL = "legal"  # courts / legal
    HEALTH = "health"
    CLIMATE = "climate"
    UNREST = "unrest"
    DIPLOMACY = "diplomacy"
    TECH = "tech"
    FINANCE = "finance"
    SPORTS_EXTERNAL = "sports_external"
    CRIME = "crime"
    OTHER = "other"


# Severity weight per category (0-1) — higher = more instability-relevant. Original.
CATEGORY_SEVERITY: dict[EventCategory, float] = {
    EventCategory.MILITARY: 1.0,
    EventCategory.UNREST: 0.9,
    EventCategory.CYBER: 0.7,
    EventCategory.LEGAL: 0.6,
    EventCategory.DIPLOMACY: 0.6,
    EventCategory.ENERGY: 0.6,
    EventCategory.ECONOMY: 0.6,
    EventCategory.ELECTIONS: 0.5,
    EventCategory.CLIMATE: 0.5,
    EventCategory.HEALTH: 0.5,
    EventCategory.FINANCE: 0.4,
    EventCategory.CRIME: 0.4,
    EventCategory.TECH: 0.3,
    EventCategory.SPORTS_EXTERNAL: 0.1,
    EventCategory.OTHER: 0.2,
}

# Ordered so higher-severity categories win when multiple patterns match.
_PATTERNS: list[tuple[EventCategory, re.Pattern[str]]] = [
    (EventCategory.MILITARY, re.compile(r"\bwar\b|invasion|missile|airstrike|troops|militar|ceasefire|nuclear", re.I)),
    (EventCategory.UNREST, re.compile(r"protest|riot|coup|uprising|unrest|insurrection|strike\b", re.I)),
    (EventCategory.CYBER, re.compile(r"cyber|hack|ransomware|breach|malware|ddos", re.I)),
    (EventCategory.LEGAL, re.compile(r"court|indict|verdict|lawsuit|trial|supreme court|ruling", re.I)),
    (EventCategory.DIPLOMACY, re.compile(r"treaty|summit|diplomat|sanction|embassy|alliance|\bun\b", re.I)),
    (EventCategory.ENERGY, re.compile(r"\boil\b|\bgas\b|opec|pipeline|energy|power grid|blackout", re.I)),
    (EventCategory.ECONOMY, re.compile(r"inflation|\bgdp\b|recession|unemployment|interest rate|\bfed\b|\bcpi\b", re.I)),
    (EventCategory.ELECTIONS, re.compile(r"election|ballot|\bvote\b|primary|nominee|referendum|\bpoll", re.I)),
    (EventCategory.CLIMATE, re.compile(r"earthquake|hurricane|flood|wildfire|storm|drought|climate|eruption", re.I)),
    (EventCategory.HEALTH, re.compile(r"pandemic|virus|vaccine|outbreak|epidemic|\bwho\b|disease", re.I)),
    (EventCategory.FINANCE, re.compile(r"bank|default|bond yield|credit|imf|bailout|currency", re.I)),
    (EventCategory.CRIME, re.compile(r"murder|shooting|assault|kidnap|trafficking|cartel", re.I)),
    (EventCategory.TECH, re.compile(r"\bai\b|semiconductor|chip\b|startup|software|satellite", re.I)),
    (EventCategory.SPORTS_EXTERNAL, re.compile(r"world cup|olympic|championship|playoff|tournament", re.I)),
]

# Country / region keyword tags (original, small set).
_REGION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("US", re.compile(r"\bunited states\b|\bu\.s\.\b|\bus\b|america|washington|white house", re.I)),
    ("EU", re.compile(r"europe|\beu\b|brussels|germany|france|\buk\b|britain|london", re.I)),
    ("MidEast", re.compile(r"israel|gaza|iran|saudi|middle east|syria|lebanon|yemen", re.I)),
    ("Asia", re.compile(r"china|taiwan|japan|korea|india|beijing|asia", re.I)),
    ("Russia", re.compile(r"russia|ukraine|moscow|kremlin|kyiv", re.I)),
    ("LatAm", re.compile(r"brazil|mexico|argentina|venezuela|latin america", re.I)),
    ("Africa", re.compile(r"nigeria|africa|sudan|egypt|ethiopia", re.I)),
]
DEFAULT_REGION = "Global"


def classify_event(text: str) -> EventCategory:
    """Rule-based classification; highest-severity matching category wins."""
    t = text or ""
    for category, pattern in _PATTERNS:  # ordered by descending severity
        if pattern.search(t):
            return category
    return EventCategory.OTHER


def extract_region(text: str) -> str:
    t = text or ""
    for region, pattern in _REGION_PATTERNS:
        if pattern.search(t):
            return region
    return DEFAULT_REGION


def category_severity(category: EventCategory) -> float:
    return CATEGORY_SEVERITY.get(category, 0.2)
