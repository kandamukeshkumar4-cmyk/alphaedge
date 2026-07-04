"""Cross-platform arbitrage opportunity service (U11).

Detects PM↔Kalshi arb *signals* from OddsSnapshot data and emits them to
the feed.  SIGNAL ONLY — no order placement, no interaction with
OrderBookService or RiskService.

Design
------
* ``detect_arb_opportunities`` is pure (no DB I/O).  It takes quote dicts
  and returns ``ArbOpportunity`` objects with a staleness guard.
* ``ArbOpportunityService`` stores detected opportunities in memory and can
  emit fresh ones to the U02 feed via ``publish_feed_item``.
* TTL is configurable; expired opportunities are marked ``stale=True``
  and never acted on — they are surfaced so the UI can grey them out.

GUARDRAILS (§G1–G3):
* No import of OrderBookService or RiskService anywhere in this module.
* No method named submit*, place*, execute*, or trade*.
* The ``signal_only=True`` field on every ``ArbOpportunity`` is a structural
  marker readable by tests.

Attribution (ideas-only, §G4 no-license repos):
  taetaehoho/arb, ImMike/polymarket-arbitrage, AlexM800/arb-bot,
  TopTrenDev/arb — README-level concept study only; no code copied.
  The service architecture and staleness guard are original.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from app.signals.arbitrage import (
    BinaryMarketQuote,
    BinaryArbitrageSignal,
    SignalCosts,
    find_binary_arbitrage,
)
from app.signals.matching import ResolutionTerms, match_resolution_terms


# ---------------------------------------------------------------------------
# Default TTL for an arb opportunity before it is marked stale.
# 5 minutes is a conservative window: PM/Kalshi prices can diverge briefly
# but converge quickly through arbitrage pressure.
# ---------------------------------------------------------------------------
DEFAULT_ARB_TTL_SECONDS: int = 300  # 5 minutes


@dataclass
class ArbOpportunity:
    """A detected PM↔Kalshi arb signal.

    ``signal_only = True`` is a STRUCTURAL INVARIANT — asserted in tests.
    It is never False; the field exists so static analysis and tests can
    confirm no code path ever sets it to False.
    """
    id: str
    pm_market_id: str
    kalshi_market_id: str
    pm_title: str
    kalshi_title: str
    match_confidence: float
    match_reasons: tuple[str, ...]
    combined_price: Decimal
    theoretical_edge: Decimal
    gross_spread: Decimal
    is_arbitrage: bool
    warning: str
    detected_at: datetime
    expires_at: datetime
    stale: bool = False
    signal_only: bool = True  # INVARIANT — never False

    def refresh_staleness(self, now: Optional[datetime] = None) -> None:
        """Mark as stale if the TTL has elapsed."""
        ts = now or datetime.now(timezone.utc)
        if ts >= self.expires_at:
            self.stale = True


@dataclass
class ArbDetectionResult:
    """Output of detect_arb_opportunities."""
    opportunities: list[ArbOpportunity]
    signal_only: bool = True  # INVARIANT


def detect_arb_opportunities(
    pm_quotes: list[dict],
    kalshi_quotes: list[dict],
    *,
    ttl_seconds: int = DEFAULT_ARB_TTL_SECONDS,
    costs: Optional[SignalCosts] = None,
    now: Optional[datetime] = None,
) -> ArbDetectionResult:
    """Pure function: match PM and Kalshi quotes and return arb signals.

    Parameters
    ----------
    pm_quotes:
        List of dicts with keys: market_id, title, yes_price, no_price,
        event_id (optional), entities (list[str] optional), close_at (optional),
        resolution_source (optional).
    kalshi_quotes:
        Same schema.
    ttl_seconds:
        How long an opportunity is fresh before being marked stale.
    costs:
        Fee model (defaults to SignalCosts()).
    now:
        Override "now" for deterministic tests.

    Returns
    -------
    ArbDetectionResult with signal_only=True (INVARIANT).
    """
    ts = now or datetime.now(timezone.utc)
    expires_at = ts + timedelta(seconds=ttl_seconds)
    opportunities: list[ArbOpportunity] = []

    for pm in pm_quotes:
        for kalshi in kalshi_quotes:
            # Build ResolutionTerms for the matcher
            pm_terms = _terms_from_dict(pm, "polymarket")
            kalshi_terms = _terms_from_dict(kalshi, "kalshi")
            match = match_resolution_terms(pm_terms, kalshi_terms)

            # We attempt arb on any pair with confidence > 0 (emit signal even
            # for unconfirmed pairs so the UI can show them with a warning).
            if match.confidence < 0.10:
                continue

            pm_quote = BinaryMarketQuote(
                platform="polymarket",
                market_id=pm["market_id"],
                yes_price=_dec(pm.get("yes_price", "0.5")),
                no_price=_dec(pm.get("no_price", "0.5")),
            )
            kalshi_quote = BinaryMarketQuote(
                platform="kalshi",
                market_id=kalshi["market_id"],
                yes_price=_dec(kalshi.get("yes_price", "0.5")),
                no_price=_dec(kalshi.get("no_price", "0.5")),
            )

            signal: BinaryArbitrageSignal = find_binary_arbitrage(
                yes_market=pm_quote,
                no_market=kalshi_quote,
                resolution_match=match,
                costs=costs,
            )

            combined = signal.yes_leg.price + signal.no_leg.price
            edge = Decimal("1.0000") - signal.net_cost

            opp = ArbOpportunity(
                id=str(uuid.uuid4()),
                pm_market_id=pm["market_id"],
                kalshi_market_id=kalshi["market_id"],
                pm_title=pm.get("title", pm["market_id"]),
                kalshi_title=kalshi.get("title", kalshi["market_id"]),
                match_confidence=match.confidence,
                match_reasons=match.reasons,
                combined_price=combined.quantize(Decimal("0.0001")),
                theoretical_edge=edge.quantize(Decimal("0.0001")),
                gross_spread=signal.gross_spread,
                is_arbitrage=signal.is_arbitrage,
                warning=signal.warning,
                detected_at=ts,
                expires_at=expires_at,
                stale=False,
                signal_only=True,  # INVARIANT
            )
            opportunities.append(opp)

    return ArbDetectionResult(opportunities=opportunities, signal_only=True)


# ---------------------------------------------------------------------------
# In-memory service (keyed by (pm_market_id, kalshi_market_id) pair)
# ---------------------------------------------------------------------------

class ArbOpportunityService:
    """Thin in-memory store for detected arb opportunities.

    Only the feed-emission path (``emit_to_feed``) performs I/O, and only
    via the ``publish_feed_item`` helper — never via OrderBookService or
    RiskService.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_ARB_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[tuple[str, str], ArbOpportunity] = {}

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def ingest(self, result: ArbDetectionResult, now: Optional[datetime] = None) -> None:
        """Upsert detected opportunities; refresh staleness on existing ones."""
        ts = now or datetime.now(timezone.utc)
        for opp in result.opportunities:
            key = (opp.pm_market_id, opp.kalshi_market_id)
            # If the pair already exists, update the prices and reset expiry.
            if key in self._store:
                existing = self._store[key]
                # Replace with fresh data — preserve id for feed de-dup.
                refreshed = ArbOpportunity(
                    id=existing.id,
                    pm_market_id=opp.pm_market_id,
                    kalshi_market_id=opp.kalshi_market_id,
                    pm_title=opp.pm_title,
                    kalshi_title=opp.kalshi_title,
                    match_confidence=opp.match_confidence,
                    match_reasons=opp.match_reasons,
                    combined_price=opp.combined_price,
                    theoretical_edge=opp.theoretical_edge,
                    gross_spread=opp.gross_spread,
                    is_arbitrage=opp.is_arbitrage,
                    warning=opp.warning,
                    detected_at=opp.detected_at,
                    expires_at=opp.expires_at,
                    stale=False,
                    signal_only=True,
                )
                self._store[key] = refreshed
            else:
                self._store[key] = opp

        # Refresh staleness for everything in the store.
        for stored in self._store.values():
            stored.refresh_staleness(ts)

    def list_all(self, now: Optional[datetime] = None) -> list[ArbOpportunity]:
        """Return all opportunities, refreshing staleness first."""
        ts = now or datetime.now(timezone.utc)
        for opp in self._store.values():
            opp.refresh_staleness(ts)
        return list(self._store.values())

    def list_fresh(self, now: Optional[datetime] = None) -> list[ArbOpportunity]:
        """Return only non-stale opportunities."""
        return [o for o in self.list_all(now=now) if not o.stale]

    async def emit_to_feed(self, opp: ArbOpportunity) -> None:
        """Publish a single arb opportunity as a feed signal (type=arb).

        This is the ONLY I/O method and it goes through the feed, never
        through OrderBookService or RiskService.
        """
        from app.api.v1.feed import FeedItem, publish_feed_item

        item = FeedItem(
            id=f"arb-{opp.id}",
            item_type="signal",
            market_slug=opp.pm_market_id,
            market_title=opp.pm_title,
            platform="polymarket",
            summary=(
                f"Arb signal: PM {opp.pm_title!r} ↔ Kalshi {opp.kalshi_title!r} "
                f"edge={float(opp.theoretical_edge):.2%} "
                f"confidence={opp.match_confidence:.0%}"
            ),
            confidence=opp.match_confidence,
            target=None,
            timestamp=opp.detected_at,
            payload={
                "signal_type": "arb",
                "pm_market_id": opp.pm_market_id,
                "kalshi_market_id": opp.kalshi_market_id,
                "match_confidence": opp.match_confidence,
                "match_reasons": list(opp.match_reasons),
                "combined_price": str(opp.combined_price),
                "theoretical_edge": str(opp.theoretical_edge),
                "is_arbitrage": opp.is_arbitrage,
                "stale": opp.stale,
                "expires_at": opp.expires_at.isoformat(),
                "signal_only": True,
                "warning": opp.warning,
            },
        )
        await publish_feed_item(item)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _terms_from_dict(d: dict, platform: str) -> ResolutionTerms:
    entities_raw = d.get("entities") or []
    return ResolutionTerms(
        platform=platform,
        market_id=d["market_id"],
        title=d.get("title", ""),
        event_id=d.get("event_id") or None,
        normalized_entities=tuple(str(e).strip().lower() for e in entities_raw),
        close_at=d.get("close_at") or None,
        resolution_source=d.get("resolution_source") or None,
    )


def _dec(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.5000")
