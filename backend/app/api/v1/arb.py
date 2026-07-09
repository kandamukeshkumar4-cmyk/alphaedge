"""Cross-platform arbitrage signal API (U11).

Exposes detected PM↔Kalshi arb opportunities as SIGNALS ONLY.

Endpoints:
  GET /api/v1/arb/opportunities   — list current (and stale) opportunities
  POST /api/v1/arb/detect         — (internal/test) run detection from quoted pairs

GUARDRAILS (§G1–G3):
* No import of OrderBookService or RiskService.
* No order-placement endpoint.  ``signal_only=True`` is present in every
  response payload.
* Stale opportunities are returned with ``stale=True`` and a staleness label
  so the UI can grey them out; they are never the basis for an action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel

from app.signals.arb_service import (
    ArbDetectionResult,
    ArbOpportunity,
    ArbOpportunityService,
    DEFAULT_ARB_TTL_SECONDS,
    detect_arb_opportunities,
)

router = APIRouter(prefix="/api/v1/arb", tags=["arb"])

# Module-level singleton service (lightweight — in-memory store).
_arb_service = ArbOpportunityService(ttl_seconds=DEFAULT_ARB_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ArbLegOut(BaseModel):
    platform: str
    market_id: str
    outcome: str
    price: str
    fee: str


class ArbOpportunityOut(BaseModel):
    id: str
    pm_market_id: str
    kalshi_market_id: str
    pm_title: str
    kalshi_title: str
    match_confidence: float
    match_reasons: list[str]
    combined_price: str
    theoretical_edge: str
    gross_spread: str
    is_arbitrage: bool
    warning: str
    detected_at: datetime
    expires_at: datetime
    stale: bool
    signal_only: bool
    seconds_until_stale: int
    # G02 additive fields (optional for older clients)
    confidence: float | None = None
    spread_bps: int = 0
    legs: list[ArbLegOut] = []


class ArbOpportunitiesPage(BaseModel):
    opportunities: list[ArbOpportunityOut]
    total: int
    fresh_count: int
    stale_count: int
    signal_only: bool = True  # INVARIANT — always True
    note: str = (
        "These are cross-platform signal observations only. "
        "AlphaEdge never auto-trades on arb signals."
    )


class DetectRequest(BaseModel):
    pm_quotes: list[dict[str, Any]]
    kalshi_quotes: list[dict[str, Any]]
    ttl_seconds: int = DEFAULT_ARB_TTL_SECONDS
    emit_to_feed: bool = False


class DetectResponse(BaseModel):
    detected: int
    signal_only: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/opportunities", response_model=ArbOpportunitiesPage)
def get_arb_opportunities(
    include_stale: bool = Query(default=True, description="Include stale (expired TTL) opportunities"),
) -> ArbOpportunitiesPage:
    """Return current PM↔Kalshi arb signal opportunities.

    Stale opportunities (TTL elapsed) are included by default so the
    frontend can show them greyed out with a countdown.  Set
    ``include_stale=false`` to return only fresh ones.
    """
    now = datetime.now(timezone.utc)
    all_opps = _arb_service.list_all(now=now)
    if not include_stale:
        all_opps = [o for o in all_opps if not o.stale]

    fresh_count = sum(1 for o in all_opps if not o.stale)
    stale_count = sum(1 for o in all_opps if o.stale)

    return ArbOpportunitiesPage(
        opportunities=[_to_out(o, now) for o in all_opps],
        total=len(all_opps),
        fresh_count=fresh_count,
        stale_count=stale_count,
        signal_only=True,
    )


@router.post("/detect", response_model=DetectResponse)
async def detect_arb(
    req: DetectRequest = Body(...),
) -> DetectResponse:
    """Detect arb opportunities from provided PM + Kalshi quotes.

    Internal/test endpoint.  The service ingests the result and optionally
    emits fresh opportunities to the U02 feed.  Never places orders.
    """
    now = datetime.now(timezone.utc)
    result: ArbDetectionResult = detect_arb_opportunities(
        pm_quotes=req.pm_quotes,
        kalshi_quotes=req.kalshi_quotes,
        ttl_seconds=req.ttl_seconds,
        now=now,
    )
    _arb_service.ingest(result, now=now)

    if req.emit_to_feed:
        fresh = _arb_service.list_fresh(now=now)
        for opp in fresh:
            await _arb_service.emit_to_feed(opp)

    return DetectResponse(detected=len(result.opportunities), signal_only=True)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _to_out(opp: ArbOpportunity, now: datetime) -> ArbOpportunityOut:
    remaining = max(0, int((opp.expires_at - now).total_seconds()))
    legs = [
        ArbLegOut(
            platform=str(leg.get("platform", "")),
            market_id=str(leg.get("market_id", "")),
            outcome=str(leg.get("outcome", "")),
            price=str(leg.get("price", "")),
            fee=str(leg.get("fee", "")),
        )
        for leg in opp.legs
    ]
    return ArbOpportunityOut(
        id=opp.id,
        pm_market_id=opp.pm_market_id,
        kalshi_market_id=opp.kalshi_market_id,
        pm_title=opp.pm_title,
        kalshi_title=opp.kalshi_title,
        match_confidence=opp.match_confidence,
        match_reasons=list(opp.match_reasons),
        combined_price=str(opp.combined_price),
        theoretical_edge=str(opp.theoretical_edge),
        gross_spread=str(opp.gross_spread),
        is_arbitrage=opp.is_arbitrage,
        warning=opp.warning,
        detected_at=opp.detected_at,
        expires_at=opp.expires_at,
        stale=opp.stale,
        signal_only=opp.signal_only,
        seconds_until_stale=remaining,
        confidence=opp.effective_confidence,
        spread_bps=opp.spread_bps,
        legs=legs,
    )
