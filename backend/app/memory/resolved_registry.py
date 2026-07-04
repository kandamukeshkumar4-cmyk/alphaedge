"""U09 — In-memory registry of resolved markets for the retrieval node.

This module maintains a deterministic, in-memory corpus of resolved markets that
the retrieval_node can query without a DB session (the graph runs synchronously in
a thread and has no async DB access).

SOURCE OF TRUTH:
  The canonical resolved markets are the seed catalog entries in
  RESOLVED_MARKET_SEED (defined here). In production, this registry would be
  refreshed from the DB at startup / on a schedule. For the paper-trading scope,
  the seed data is the available corpus.

REAL RESOLVED MARKETS ONLY:
  No fabricated entries. Only markets with a verified winning_outcome in the
  seed data are included. The ticker "nba-2025-01-15-lal-bos" is the canonical
  test market (Lakers win = YES). Additional seed entries mirror the catalog.

DETERMINISM:
  Same slug query → same feature vector. Same resolved corpus → same ranked
  candidates. Tests verify this invariant.

NO ORDER-PATH IMPORTS. NO DB SESSION.
"""
from __future__ import annotations

from typing import Optional

from app.memory.retrieval import MarketFeatureVector

# ---------------------------------------------------------------------------
# Seed catalog of known markets (feature vectors for similarity)
# ---------------------------------------------------------------------------
# These are the same markets in CATALOG_SLUGS / CATALOG_MAP.
# Category values match the Market.category field in the DB.

_MARKET_CATALOG: dict[str, dict] = {
    "nba-2025-01-15-lal-bos": {
        "title": "Lakers vs Celtics — Lakers Win?",
        "category": "NBA",
        "tournament_tag": None,
    },
    "nba-warriors-playoff-seed": {
        "title": "Warriors to secure top-4 playoff seed?",
        "category": "NBA",
        "tournament_tag": None,
    },
    "elect-la-mayor-2026": {
        "title": "Will the Democratic candidate win LA Mayor 2026?",
        "category": "Elections",
        "tournament_tag": None,
    },
    "elect-2028-dem-nominee": {
        "title": "2028 Democratic Presidential Nominee",
        "category": "Elections",
        "tournament_tag": None,
    },
    "wc2026-m1-mex-homewin": {
        "title": "FIFA WC2026 Mexico Home Win — Group Stage",
        "category": "FIFA WC2026",
        "tournament_tag": "wc2026",
    },
    "wc2026-m1-draw": {
        "title": "FIFA WC2026 Group Stage Match Draw",
        "category": "FIFA WC2026",
        "tournament_tag": "wc2026",
    },
    "wc2026-m1-rsa-awaywin": {
        "title": "FIFA WC2026 RSA Away Win — Group Stage",
        "category": "FIFA WC2026",
        "tournament_tag": "wc2026",
    },
    "wc2026-winner-brazil": {
        "title": "Brazil to Win FIFA World Cup 2026",
        "category": "FIFA WC2026",
        "tournament_tag": "wc2026",
    },
    "wc2026-winner-france": {
        "title": "France to Win FIFA World Cup 2026",
        "category": "FIFA WC2026",
        "tournament_tag": "wc2026",
    },
    "wc2026-winner-argentina": {
        "title": "Argentina to Win FIFA World Cup 2026",
        "category": "FIFA WC2026",
        "tournament_tag": "wc2026",
    },
    "crypto-btc-friday-5pm": {
        "title": "BTC above $70 000 on Friday 5pm?",
        "category": "Crypto",
        "tournament_tag": None,
    },
    "crypto-eth-100k-eoy": {
        "title": "ETH above $100 000 end of year?",
        "category": "Crypto",
        "tournament_tag": None,
    },
    "culture-gta6-trailer": {
        "title": "GTA 6 trailer released by end of 2025?",
        "category": "Culture",
        "tournament_tag": None,
    },
    "culture-love-island-elim": {
        "title": "Love Island next elimination outcome",
        "category": "Culture",
        "tournament_tag": None,
    },
    "econ-cpi-above-3": {
        "title": "CPI above 3% in Q1 2025?",
        "category": "Economics",
        "tournament_tag": None,
    },
    "econ-fed-cut-march": {
        "title": "Fed rate cut in March 2025?",
        "category": "Economics",
        "tournament_tag": None,
    },
}

# ---------------------------------------------------------------------------
# Resolved market seed: REAL resolved markets with confirmed outcomes.
# Each entry: slug → {winning_outcome, resolved_at_iso, last_predicted_prob}
# winning_outcome: "YES" | "NO" (string form of OrderOutcome)
# last_predicted_prob: float | None (model prediction at last snapshot, if known)
# resolved_at_iso: ISO date string
#
# TRUTH-FIRST: only the canonical test market has a confirmed outcome in
# tests (nba-2025-01-15-lal-bos → YES per the canonical test spec). Other
# entries are left unresolved (not included) — no fabricated resolutions.
# ---------------------------------------------------------------------------

_RESOLVED_SEED: dict[str, dict] = {
    # Canonical test market — spec: Lakers win resolves YES at $1.
    "nba-2025-01-15-lal-bos": {
        "winning_outcome": "YES",
        "resolved_at_iso": "2025-01-15",
        "last_predicted_prob": 0.65,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_query_feature_vector(slug: str) -> MarketFeatureVector:
    """Return the MarketFeatureVector for a market slug.

    Falls back to a minimal vector (category=Sports, no tag) if the slug is
    not in the catalog. This ensures the retrieval node never hard-fails.
    """
    data = _MARKET_CATALOG.get(slug, {})
    return MarketFeatureVector(
        slug=slug,
        title=data.get("title", slug),
        category=data.get("category", "Sports"),
        tournament_tag=data.get("tournament_tag"),
    )


def get_resolved_candidates(
    *, exclude_slug: str = ""
) -> list[tuple[MarketFeatureVector, str, Optional[float], str]]:
    """Return the list of resolved-market candidates for similarity ranking.

    Each tuple: (feature_vector, outcome_str, predicted_prob, resolved_at_iso)

    Only markets present in _RESOLVED_SEED are returned (real resolutions only).
    The exclude_slug market is always excluded (avoids self-retrieval).
    """
    candidates = []
    for slug, resolution in _RESOLVED_SEED.items():
        if slug == exclude_slug:
            continue
        fv = get_query_feature_vector(slug)
        outcome_str: str = resolution.get("winning_outcome", "unknown")
        pred_prob: Optional[float] = resolution.get("last_predicted_prob")
        resolved_at: str = resolution.get("resolved_at_iso", "")
        candidates.append((fv, outcome_str, pred_prob, resolved_at))
    return candidates


def register_resolved_market(
    slug: str,
    winning_outcome: str,
    *,
    last_predicted_prob: Optional[float] = None,
    resolved_at_iso: str = "",
) -> None:
    """Register a newly resolved market into the in-memory registry.

    Called by the market resolution pathway after a market resolves, so the
    registry stays current without a process restart.

    winning_outcome: "YES" | "NO" (case-insensitive; stored as uppercase).
    Idempotent: re-registering the same slug updates the entry.
    """
    _RESOLVED_SEED[slug] = {
        "winning_outcome": winning_outcome.upper(),
        "resolved_at_iso": resolved_at_iso,
        "last_predicted_prob": last_predicted_prob,
    }
