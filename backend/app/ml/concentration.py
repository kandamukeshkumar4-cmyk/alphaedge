"""V40 market-family and correlation-cluster normalization for serving code.

This mirrors the read-only concentration snapshot's normalization contract: one
market family resolving on one stamped date is one effective observation.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|"
    "november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_DATE_PATTERNS = [
    re.compile(rf"-on-(?:{_MONTHS})-\d{{1,2}}(?:-\d{{4}})?$"),
    re.compile(rf"-(?:{_MONTHS})-\d{{1,2}}(?:-(?:{_MONTHS})-\d{{1,2}})?(?:-\d{{4}})?$"),
    re.compile(r"-\d{4}-\d{2}-\d{2}$"),
    re.compile(rf"-in-(?:{_MONTHS})(?:-\d{{4}})?$"),
]
_STRIKE_PATTERNS = [
    re.compile(r"-\d+(?:\.\d+)?[km]$"),
    re.compile(r"-\d+(?:\.\d+)?[km]?\-\d+(?:\.\d+)?[km]?$"),
    re.compile(r"-\d+(?:\.\d+)?-?(?:percent|pct|bps)$"),
    re.compile(r"-\d+(?:\.\d+)?$"),
]


def market_family(external_id: str) -> str:
    slug = (external_id or "").strip().lower()
    changed = True
    while changed:
        changed = False
        for pattern in (*_DATE_PATTERNS, *_STRIKE_PATTERNS):
            stripped = pattern.sub("", slug)
            if stripped != slug and stripped:
                slug = stripped
                changed = True
    return slug or (external_id or "").strip().lower()


def correlation_cluster(external_id: str) -> str:
    slug = (external_id or "").strip().lower()
    stamp = ""
    for pattern in _DATE_PATTERNS:
        match = pattern.search(slug)
        if match:
            stamp = match.group(0).lstrip("-")
            break
    family = market_family(external_id)
    return f"{family}|{stamp}" if stamp else family


def build_report(rows: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    n = len(rows)
    categories = Counter(str(row.get("category") or "Uncategorized") for row in rows)
    venues = Counter(str(row.get("platform") or "unknown") for row in rows)
    families = Counter(market_family(str(row.get("external_id") or "")) for row in rows)
    clusters = Counter(correlation_cluster(str(row.get("external_id") or "")) for row in rows)
    top_share = categories.most_common(1)[0][1] / n if n else 0.0

    def histogram(counter: Counter) -> list[dict[str, Any]]:
        return [
            {"key": key, "n": count, "share": round(count / n, 4) if n else 0.0}
            for key, count in counter.most_common()
        ]

    report: dict[str, Any] = {
        "mode": mode,
        "scored_population_n": n,
        "category_histogram": histogram(categories),
        "venue_histogram": histogram(venues),
        "distinct_families": len(families),
        "family_histogram": histogram(families),
        "correlation_clusters": len(clusters),
        "cluster_histogram": histogram(clusters),
        "effective_n_estimate": len(clusters),
        "effective_n_ratio": round(len(clusters) / n, 4) if n else 0.0,
    }
    horizons = [
        (row["close_at"] - row["locked_at"]).total_seconds() / 3600.0
        for row in rows
        if row.get("close_at") and row.get("locked_at")
    ]
    if horizons:
        horizons.sort()
        report["horizon_hours"] = {
            "n": len(horizons),
            "min": round(horizons[0], 2),
            "median": round(horizons[len(horizons) // 2], 2),
            "max": round(horizons[-1], 2),
            "under_24h_share": round(sum(hour <= 24 for hour in horizons) / len(horizons), 4),
        }
    checks = {
        "no_category_over_40pct": top_share <= 0.40,
        "distinct_families_at_least_20": len(families) >= 20,
        "correlation_clusters_at_least_20": len(clusters) >= 20,
    }
    report["checks"] = checks
    report["verdict"] = (
        "USABLE — composition checks pass"
        if all(checks.values())
        else "CONCENTRATED — a Brier over this sample cannot discriminate models; "
        "per E06 report both Briers and declare NO WINNER"
    )
    return report
