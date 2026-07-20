from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CLVRecordResponse(BaseModel):
    market_slug: str
    model_prob: float
    closing_prob: Optional[float]
    clv: Optional[float]
    resolved_at: Optional[datetime]
    is_edge: bool


class CLVTrackRecordResponse(BaseModel):
    paper_trading_only: bool = True
    disclaimer: str
    records: list[CLVRecordResponse]


class PaperPnlSummaryResponse(BaseModel):
    total_pnl: float
    n_bets: int
    win_rate: float
    note: str
    disclaimer: str
    paper_trading_only: bool = True


class SignalFeedOutcome(BaseModel):
    """One outcome row for the Polymarket-style alert card (Loop V78 N1).

    ``price`` is a REAL stored odds-snapshot probability (never fabricated);
    ``image_url`` is the venue's own image for the market subject, or None —
    the UI falls back to the glyph token when it is absent. Never a
    fabricated face."""

    name: str
    price: float
    image_url: Optional[str] = None


class SignalFeedItemResponse(BaseModel):
    id: str
    signal_type: str
    platform: str
    market_id: str
    market_name: str
    implied_edge: Optional[float]
    sample_size: int
    is_edge: bool
    provisional: bool
    created_at: datetime
    resolved: bool
    # Loop V78 (N1) — additive display enrichment composed from stored rows
    # (markets + odds_snapshots). All None/empty when the signal's market is
    # not mirrored locally: honest omission, never invented numbers/imagery.
    market_title: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    volume: Optional[int] = None
    traders: Optional[int] = None
    market_count: Optional[int] = None
    outcomes: list[SignalFeedOutcome] = []


class SignalFeedResponse(BaseModel):
    paper_trading_only: bool = True
    disclaimer: str
    signals: list[SignalFeedItemResponse]
    # Additive (Loop V21 P2): true when served from in-process TTL cache.
    cached: bool = False


class SignalsDashboardResponse(BaseModel):
    paper_trading_only: bool = True
    disclaimer: str
    signals: list[SignalFeedItemResponse]
    clv_records: list[CLVRecordResponse]
    paper_pnl: PaperPnlSummaryResponse
    llm_explanation: Optional[str] = Field(
        default=None,
        description="Phase 4 stub — populated when LLM explain module is wired",
    )
