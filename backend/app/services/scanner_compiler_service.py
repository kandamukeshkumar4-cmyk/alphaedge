"""Deterministic NL → scanner alert-spec compiler (v1, no LLM).

Keyword parsing only. Always returns a valid spec-shaped dict; unknown phrases
land in ``notes`` rather than raising.
"""
from __future__ import annotations

import re
from typing import Any

_SIGNAL_TYPES = frozenset({"WHALE_FLOW", "PRICE_TREND", "NEWS_SENTIMENT", "MODEL_EDGE"})

_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "with",
        "for",
        "of",
        "to",
        "in",
        "on",
        "at",
        "when",
        "show",
        "shows",
        "scan",
        "scanner",
        "alert",
        "me",
        "markets",
        "market",
        "above",
        "min",
        "minimum",
        "volume",
        "every",
        "minutes",
        "minute",
        "hours",
        "hour",
        "daily",
        "top",
        "day",
        "days",
        "window",
    }
)

_KNOWN = frozenset(
    {
        "whale",
        "flow",
        "trend",
        "momentum",
        "price",
        "news",
        "sentiment",
        "model",
        "edge",
        "nba",
        "sports",
        "election",
        "crypto",
    }
)


def _default_spec() -> dict[str, Any]:
    return {
        "name": "Untitled scanner",
        "universe": {"categories": [], "minimum_volume": 0},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": False,
            "interval_minutes": 60,
        },
        "steps": [],
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
        "limit": 20,
        "notes": [],
    }


def compile_scanner_spec(text: str) -> dict[str, Any]:
    """Compile plain English into a versioned alert specification dict.

    Never fails: unrecognised phrases are listed under ``notes``.
    """
    raw = (text or "").strip()
    lower = raw.lower()
    out = _default_spec()
    if not raw:
        out["notes"] = ["(empty)"]
        return out

    # Short display name from the request (first clause / 80 chars).
    name_src = re.split(r"[.!?\n]", raw, maxsplit=1)[0].strip()
    out["name"] = (name_src[:80] or "Untitled scanner").strip()

    steps: list[dict[str, Any]] = []

    if re.search(r"\bwhale\b|\bflow\b", lower):
        steps.append({"type": "WHALE_FLOW"})

    if re.search(r"\btrend\b|\bmomentum\b|\bprice\b", lower):
        window_days = 7
        m_win = re.search(r"(\d+)\s*days?", lower)
        if m_win:
            window_days = int(m_win.group(1))
        steps.append({"type": "PRICE_TREND", "window_days": window_days})

    if re.search(r"\bnews\b|\bsentiment\b", lower):
        steps.append({"type": "NEWS_SENTIMENT"})

    if re.search(r"\bmodel\b|\bedge\b", lower):
        steps.append({"type": "MODEL_EDGE"})

    signal_count = sum(1 for s in steps if s.get("type") in _SIGNAL_TYPES)
    if signal_count >= 2:
        steps.append({"type": "DIRECTION_ALIGNMENT"})
    out["steps"] = steps

    categories: list[str] = []
    for cat in ("nba", "sports", "election", "crypto"):
        if re.search(rf"\b{re.escape(cat)}\b", lower):
            categories.append(cat)
    out["universe"]["categories"] = categories

    min_vol = 0
    m_vol = re.search(r"volume\s+above\s+(\d[\d,]*)", lower)
    if not m_vol:
        m_vol = re.search(r"min(?:imum)?\s+volume(?:\s+of)?\s+(\d[\d,]*)", lower)
    if m_vol:
        min_vol = int(m_vol.group(1).replace(",", ""))
    out["universe"]["minimum_volume"] = min_vol

    interval = 60
    if re.search(r"\bdaily\b", lower):
        interval = 1440
    else:
        m_min = re.search(r"every\s+(\d+)\s*minutes?", lower)
        m_hr = re.search(r"every\s+(\d+)\s*hours?", lower)
        if m_min:
            interval = int(m_min.group(1))
        elif m_hr:
            interval = int(m_hr.group(1)) * 60
    out["schedule"]["interval_minutes"] = interval

    limit = 20
    m_top = re.search(r"\btop\s+(\d+)\b", lower)
    if m_top:
        limit = int(m_top.group(1))
    out["limit"] = limit

    # Residual tokens that are not known keywords / stopwords / pure numbers.
    notes: list[str] = []
    for tok in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", lower):
        if tok.isdigit():
            continue
        if tok in _STOP or tok in _KNOWN:
            continue
        if tok not in notes:
            notes.append(tok)
    out["notes"] = notes
    return out
