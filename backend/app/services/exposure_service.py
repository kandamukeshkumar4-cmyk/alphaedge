"""Portfolio exposure aggregation for U04.

Deterministic, read-only math. Groups open paper positions by correlated
underlier, computes net directional exposure, and flags concentration risk.

Correlation key derivation is fully deterministic — no LLM involved.  LLM
narration is optional and lives in the API layer (not here).

Design notes (adapted from guangxiangdebizi/PolyMarket-MCP position-tracking
tool shapes — MIT licence; ideas adapted, no code copied):
- Underlier key is inferred purely from market slug / category string.
- Net exposure direction: YES shares count positive, NO shares count negative.
- Notional = shares × avg_cost (cost basis, not mark-to-market) for
  concentration purposes.  Mark-to-market would require live prices and adds
  complexity without changing the ranking.
- Concentration threshold: >40 % of total open notional in a single underlier.

PAPER_TRADING_ONLY — this module must NEVER import OrderBookService or
RiskService.  It reads only position data passed as arguments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Underlier derivation ──────────────────────────────────────────────────────

# NBA team abbreviations recognised in slug patterns like
#   nba-2025-01-15-lal-bos, nba-*-gsw-*, etc.
_NBA_TEAMS: frozenset[str] = frozenset(
    [
        "atl", "bos", "bkn", "cha", "chi", "cle", "dal", "den", "det",
        "gsw", "hou", "ind", "lac", "lal", "mem", "mia", "mil", "min",
        "nop", "nyk", "okc", "orl", "phi", "phx", "por", "sac", "sas",
        "tor", "uta", "was",
    ]
)

# FIFA WC2026 groups
_FIFA_GROUP_RE = re.compile(r"fifa.*wc.*group[- _]?([a-p])\b", re.IGNORECASE)

# Crypto underlier keywords
_CRYPTO_RE = re.compile(
    r"\b(btc|bitcoin|eth|ethereum|sol|solana|bnb|xrp|usdc|doge|ada)\b",
    re.IGNORECASE,
)

# US election keywords — plural-aware (elections, votes, etc.)
_ELECTION_RE = re.compile(
    r"\b(president|senate|house|governor|elections?|ballot|votes?|dem|rep)\b",
    re.IGNORECASE,
)


def derive_underlier_key(slug: str, category: str | None = None) -> str:
    """Return a deterministic correlation key for a market.

    Rules (checked in priority order):
    1. NBA team — e.g. "nba-2025-01-15-lal-bos" → "NBA:LAL" (home team, first)
    2. FIFA WC2026 group — "fifa-wc2026-group-a-*" → "FIFA_WC2026:GROUP_A"
    3. Crypto — any slug containing btc/eth/sol/… → "CRYPTO:<SYMBOL>"
    4. Election — slug or category contains election keywords → "ELECTIONS"
    5. Category fallback — capitalise the DB category string → e.g. "SPORTS"
    6. Default → "OTHER"
    """
    slug_lower = slug.lower()

    # 1. NBA
    if "nba" in slug_lower or (category and "nba" in category.lower()):
        parts = slug_lower.replace("-", " ").split()
        for part in parts:
            if part in _NBA_TEAMS:
                return f"NBA:{part.upper()}"
        return "NBA:OTHER"

    # 2. FIFA WC2026
    m = _FIFA_GROUP_RE.search(slug_lower)
    if m:
        return f"FIFA_WC2026:GROUP_{m.group(1).upper()}"
    if "fifa" in slug_lower or "wc2026" in slug_lower or (
        category and "fifa" in category.lower()
    ):
        return "FIFA_WC2026:OTHER"

    # 3. Crypto
    m = _CRYPTO_RE.search(slug_lower)
    if m:
        return f"CRYPTO:{m.group(1).upper()}"

    # 4. Elections
    if _ELECTION_RE.search(slug_lower) or (
        category and _ELECTION_RE.search(category)
    ):
        return "ELECTIONS"

    # 5. Category fallback
    if category and category.strip():
        return category.strip().upper().replace(" ", "_")

    return "OTHER"


# ── Data shapes ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PositionInput:
    """One open position passed to the exposure engine."""
    market_slug: str
    outcome: str          # "yes" or "no"
    shares: float
    avg_cost: float       # cost basis per share
    category: str | None = None


@dataclass
class ExposureGroup:
    """Aggregated exposure for one correlated underlier."""
    underlier: str
    position_count: int
    net_directional: float   # +ve = net YES; -ve = net NO; notional ($)
    total_notional: float    # absolute sum (regardless of direction)
    pct_of_total: float      # 0.0–100.0
    concentrated: bool       # True when pct_of_total > CONCENTRATION_THRESHOLD_PCT
    positions: list[str] = field(default_factory=list)  # market slugs


CONCENTRATION_THRESHOLD_PCT: float = 40.0


@dataclass(frozen=True)
class ExposureSummary:
    total_open_notional: float
    groups: list[ExposureGroup]
    has_concentration: bool
    concentrated_underliers: list[str]
    paper_trading_only: bool = True
    disclaimer: str = (
        "Research only — not financial advice. "
        "Exposure figures are cost-basis notional, not mark-to-market. "
        "Paper trading only."
    )


# ── Core aggregation ──────────────────────────────────────────────────────────

def compute_exposure(
    positions: list[PositionInput],
    *,
    concentration_threshold_pct: float = CONCENTRATION_THRESHOLD_PCT,
) -> ExposureSummary:
    """Aggregate open positions by underlier and return exposure groups.

    ``net_directional`` sign convention:
      - YES shares contribute +notional  (long YES = bullish on the event)
      - NO  shares contribute -notional  (long NO  = short the event)

    ``total_notional`` is the absolute value used for concentration math,
    so a book that is $50 long YES and $50 long NO on the same underlier
    has $100 total notional but $0 net — still concentrated notionally.
    """
    if not positions:
        return ExposureSummary(
            total_open_notional=0.0,
            groups=[],
            has_concentration=False,
            concentrated_underliers=[],
        )

    # Group by underlier
    by_underlier: dict[str, dict] = {}
    for pos in positions:
        key = derive_underlier_key(pos.market_slug, pos.category)
        notional = pos.shares * pos.avg_cost
        directional = notional if pos.outcome.lower() == "yes" else -notional

        if key not in by_underlier:
            by_underlier[key] = {
                "net": 0.0,
                "abs": 0.0,
                "slugs": set(),
            }
        by_underlier[key]["net"] += directional
        by_underlier[key]["abs"] += abs(notional)
        by_underlier[key]["slugs"].add(pos.market_slug)

    total_open = sum(v["abs"] for v in by_underlier.values())

    groups: list[ExposureGroup] = []
    for underlier, data in by_underlier.items():
        pct = (data["abs"] / total_open * 100.0) if total_open > 0 else 0.0
        groups.append(
            ExposureGroup(
                underlier=underlier,
                position_count=len(data["slugs"]),
                net_directional=round(data["net"], 4),
                total_notional=round(data["abs"], 4),
                pct_of_total=round(pct, 2),
                concentrated=pct > concentration_threshold_pct,
                positions=sorted(data["slugs"]),
            )
        )

    # Sort descending by total_notional
    groups.sort(key=lambda g: g.total_notional, reverse=True)

    concentrated = [g.underlier for g in groups if g.concentrated]
    return ExposureSummary(
        total_open_notional=round(total_open, 4),
        groups=groups,
        has_concentration=bool(concentrated),
        concentrated_underliers=concentrated,
    )
