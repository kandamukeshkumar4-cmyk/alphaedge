"""U05 — Analysis-only assistant chat endpoint.

POST /api/v1/assistant/chat

Answers market / portfolio questions using ONLY read-only context: news/whale/
instability signals from the agent graph, the U04 exposure data, analyst briefs
from the T12 public API, and the U03 agent-trace.

HARD GUARDRAILS (§G U05):
- This module does NOT import OrderBookService, RiskService, or submit_order_intent.
- ASSISTANT_ALLOWED_TOOLS is read-only ONLY — submit_order_intent is excluded.
- The endpoint is structurally incapable of emitting an order intent.
- Works with no LLM key via a deterministic fallback (same pattern as the analyst
  in T07 / predictor).

Study / attribution: CloddsBot (MIT) — chat-agent UX patterns (no code copied);
berlinbra/polymarket-mcp + artvandelay/polymarket-agents (MIT) — read-only tool
shapes for the allowlist.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from typing import Any

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_user
from app.core.config import get_settings
from app.db.models import AnalystBrief, Market, OddsSnapshot, PredictionLog, User
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["assistant"])

# ── Read-only tool allowlist ─────────────────────────────────────────────────
# IMPORTANT: submit_order_intent is intentionally ABSENT.  Any attempt to add
# order tools here violates §G2 and must be rejected in code review.

ASSISTANT_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "get_odds",
        "get_features",
        "get_exposure",
        "get_briefs",
        "get_agent_trace",
        "get_trader_profile",
    }
)

# Verify — this assertion is also tested in test_assistant_chat.py.
assert "submit_order_intent" not in ASSISTANT_ALLOWED_TOOLS, (
    "submit_order_intent must NEVER appear in ASSISTANT_ALLOWED_TOOLS"
)

ANALYSIS_ONLY_BANNER = "Analysis only — this assistant cannot place trades."
PAPER_ONLY_DISCLAIMER = "Paper trading only — simulated funds, no execution."
_MENU_MARKER = "I can help with:"
_ANALYZE_KEYWORDS = ("analyze", "deep-dive", "deep dive")
_BEAR_KEYWORDS = ("bear", "downside", "against")
_EXPOSURE_KEYWORDS = ("exposure", "position", "portfolio", "risk")
_ASSISTANT_PREDICTION_CACHE_TTL_SEC = 60.0

# ── Anonymous per-IP rate limiter ────────────────────────────────────────────
# The chat endpoint keeps an anonymous public path (the demo works with no
# login). Authenticated requests bypass this; anonymous traffic is bounded per
# IP via a simple in-memory fixed-window counter. Process-local by design —
# fine for a single API process and zero-external-state on the free tier.
_ANON_WINDOW_SEC = 60.0
_anon_window: dict[str, tuple[int, float]] = {}

# Injectable clock so tests can pin the window (slow CI runs otherwise let
# sequential requests straddle a window boundary).
_anon_clock = time.monotonic


_ANON_PRUNE_THRESHOLD = 100


def _client_ip(request: Request) -> str:
    """Best-effort client IP behind HF / Vercel proxies.

    HF Spaces and Vercel rewrites share one edge IP on ``request.client.host``,
    which collapses the anon chat budget for every visitor. Prefer the first
    X-Forwarded-For hop when present.
    """
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
    if real and real.strip():
        return real.strip()
    return request.client.host if request.client else "unknown"


def _anon_allowed(ip: str, limit: int) -> bool:
    """Fixed-window per-IP counter. Returns True when the request is allowed."""
    now = _anon_clock()
    count, start = _anon_window.get(ip, (0, now))
    if now - start >= _ANON_WINDOW_SEC:
        count, start = 0, now
    if count >= limit:
        _anon_window[ip] = (count, start)
        return False
    _anon_window[ip] = (count + 1, start)
    # Light-weight stale-entry prune so the dict never grows unbounded.
    if len(_anon_window) > _ANON_PRUNE_THRESHOLD:
        _prune_stale_anon_entries(now)
    return True


def _prune_stale_anon_entries(now: float | None = None) -> None:
    """Remove IPs whose window has expired."""
    now = now or time.monotonic()
    stale = [ip for ip, (_, start) in _anon_window.items() if now - start >= _ANON_WINDOW_SEC]
    for ip in stale:
        del _anon_window[ip]


def _reset_anon_rate_limiter() -> None:
    """Clear the in-memory anon rate-limit state (test helper)."""
    _anon_window.clear()

# ── Schemas ──────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    market_slug: str | None = Field(default=None, description="Scope to a specific market")
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    # U13: optional serialised profile context injected by the caller.
    # The profile NUMBERS come from the deterministic trader_profile_service;
    # the assistant NARRATES them — it never invents stats.
    trader_profile_context: dict | None = Field(
        default=None,
        description="Pre-fetched trader profile dict (from /api/v1/profile). "
        "When provided, the assistant may reference the user's trading patterns.",
    )


class CitationChip(BaseModel):
    source: str
    label: str


class AssistantChatResponse(BaseModel):
    reply: str
    citations: list[CitationChip] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    paper_trading_only: bool = True
    analysis_only_banner: str = ANALYSIS_ONLY_BANNER


# ── Context assembly ─────────────────────────────────────────────────────────


def _gather_market_context(slug: str) -> dict[str, Any]:
    """Collect read-only signals for a market slug without touching the DB."""
    ctx: dict[str, Any] = {"slug": slug}

    # News signal (cached — see graph.py news_node)
    try:
        from app.signals.news_signal import get_cached_signal

        signal = get_cached_signal(slug)
        if signal is not None:
            ctx["news_sentiment"] = signal.sentiment_score
            ctx["news_volume"] = signal.volume_score
            ctx["news_headline"] = signal.headline
    except Exception:
        pass

    return ctx


def _is_analyze_intent(message: str) -> bool:
    """True for AI Analyze / deep-dive seed prompts from the market cards."""
    msg = message.lower()
    return any(kw in msg for kw in _ANALYZE_KEYWORDS)


def _is_bear_intent(message: str) -> bool:
    return any(kw in message.lower() for kw in _BEAR_KEYWORDS)


def _is_exposure_intent(message: str) -> bool:
    return any(kw in message.lower() for kw in _EXPOSURE_KEYWORDS)


def _humanize_signal_type(signal_type: str) -> str:
    """Mirror frontend signalLabel (signal-rail.ts): last ':' segment, title-cased."""
    raw = signal_type.rsplit(":", 1)[-1] if ":" in signal_type else signal_type
    words = re.sub(r"[_-]+", " ", raw).strip()
    return " ".join(w[:1].upper() + w[1:] for w in words.split(" ")) or signal_type


def _signal_payload_direction(payload: dict[str, Any]) -> str | None:
    """Mirror frontend directionOf: payload.direction → UP/DOWN, else None."""
    raw = payload.get("direction")
    if not isinstance(raw, str):
        return None
    low = raw.lower()
    if low in ("up", "buy", "long", "positive"):
        return "UP"
    if low in ("down", "sell", "short", "negative"):
        return "DOWN"
    return None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    return f if math.isfinite(f) else None


def _signed_label(value: float, suffix: str) -> str:
    """Mirror frontend signedLabel: +/- sign, 0 or 1 decimal place."""
    rounded = (
        f"{value:.0f}" if abs(value) >= 100 or float(value).is_integer() else f"{value:.1f}"
    )
    return f"{'+' if value > 0 else ''}{rounded}{suffix}"


def _signal_magnitude_label(payload: dict[str, Any], direction: str | None) -> str | None:
    """Mirror frontend magnitudeLabel; None (honest omission) when nothing present."""

    def signed(value: float) -> float:
        if direction == "UP":
            return abs(value)
        if direction == "DOWN":
            return -abs(value)
        return value

    detail = payload.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    bps = _finite(detail.get("bps"))
    if bps is None:
        bps = _finite(payload.get("move_bps"))
    if bps is not None:
        return _signed_label(signed(bps), " bps")

    magnitude = _finite(payload.get("magnitude"))
    if magnitude is not None:
        if abs(magnitude) <= 1:
            return _signed_label(signed(magnitude * 100), "¢")
        return _signed_label(signed(magnitude), "")

    for key in ("score", "confidence", "edge"):
        value = _finite(payload.get(key))
        if value is not None:
            return f"{key} {value:.2f}"
    return None


def _lean_label(model_p: float | None, market_p: float | None) -> str:
    if model_p is None or market_p is None:
        return "neutral"
    diff = model_p - market_p
    if abs(diff) < 0.02:
        return "neutral"
    return "favors YES" if diff > 0 else "favors NO"


async def _prediction_context_for_analyze(
    slug: str, db: AsyncSession
) -> dict[str, Any]:
    """Return a stored forecast or run the existing prediction pipeline once.

    The public market-prediction endpoint runs this same pipeline for catalog
    markets.  Assistant Analyze first prefers an already-persisted forecast,
    then uses a short in-process cache around that pipeline so repeated chat
    prompts cannot repeatedly trigger feature/model work.
    """
    try:
        stored = await db.scalar(
            select(PredictionLog)
            .where(PredictionLog.market_slug == slug)
            .order_by(PredictionLog.predicted_at.desc())
            .limit(1)
        )
    except Exception as exc:
        logger.debug("assistant stored prediction lookup failed for %s: %s", slug, exc)
        stored = None

    if stored is not None:
        return {
            "model_prob": round(float(stored.predicted_prob), 4),
            "confidence": round(float(stored.confidence), 4),
            "forecast_reason": "latest stored prediction",
            "prediction_source": "stored",
        }

    from app.core import leaderboard_cache

    cache_key = ("assistant-on-demand-prediction", slug)
    cached = leaderboard_cache.get(cache_key, _ASSISTANT_PREDICTION_CACHE_TTL_SEC)
    if isinstance(cached, dict):
        return dict(cached)

    try:
        from app.api.v1.market_prediction import _implied_prob_from_catalog
        from app.forecasting.predictor import predict_market
        from app.services.market_service import CATALOG_SLUGS

        if slug not in CATALOG_SLUGS:
            return {
                "unscorable_reason": "this market is outside the prediction catalog",
            }
        prediction = await asyncio.to_thread(
            predict_market,
            {"market_slug": slug, "implied_yes": _implied_prob_from_catalog(slug)},
        )
        result = {
            "model_prob": round(float(prediction.predicted_prob), 4),
            "confidence": round(float(prediction.confidence), 4),
            "is_edge": prediction.is_edge,
            "forecast_reason": prediction.reason,
            "prediction_source": "on-demand",
        }
        # Match leaderboard_cache semantics: cache only a successful pipeline result.
        leaderboard_cache.put(cache_key, result)
        return result
    except Exception as exc:
        logger.debug("assistant on-demand prediction failed for %s: %s", slug, exc)
        return {
            "unscorable_reason": "the prediction pipeline could not score its available features",
        }


async def _enrich_bear_case_context(
    slug: str, ctx: dict[str, Any], db: AsyncSession
) -> dict[str, Any]:
    """Add bear-case facts solely from existing market and signal stores."""
    out = dict(ctx)
    negative_drivers = [
        driver for driver in out.get("drivers", []) if driver.get("direction") == "favors NO"
    ]
    if negative_drivers:
        out["negative_drivers"] = negative_drivers[:3]

    try:
        market = await db.scalar(select(Market).where(Market.slug == slug).limit(1))
        if market is not None:
            if market.lock_at is not None:
                lock_at = market.lock_at
                if lock_at.tzinfo is None:
                    lock_at = lock_at.replace(tzinfo=UTC)
                out["hours_to_close"] = round(
                    (lock_at - datetime.now(UTC)).total_seconds() / 3600, 2
                )
            target_volume = float(market.volume or 0)
            volumes = [
                float(value) for value in (await db.scalars(select(Market.volume))).all()
                if value is not None
            ]
            if len(volumes) > 1:
                out["volume_percentile"] = round(
                    sum(value <= target_volume for value in volumes) / len(volumes) * 100,
                    1,
                )
    except Exception as exc:
        logger.debug("bear-case market depth lookup failed for %s: %s", slug, exc)
    return out


async def _enrich_exposure_context(
    slug: str, ctx: dict[str, Any], user: User, db: AsyncSession
) -> dict[str, Any]:
    """Attach deterministic, authenticated paper-position math for one market."""
    out = dict(ctx)
    try:
        from app.api.v1.portfolio import _load_paper_orders

        open_positions = [
            position
            for position in await _load_paper_orders(db, user.id.hex)
            if not position.settled and position.shares > 0 and position.cost > 0
        ]
        market_positions = [position for position in open_positions if position.market_slug == slug]
        total_open_notional = sum(position.cost for position in open_positions)
        market_notional = sum(position.cost for position in market_positions)
        out["exposure_authenticated"] = True
        out["market_positions"] = [
            {
                "outcome": position.outcome.upper(),
                "shares": round(position.shares, 4),
                "avg_cost": round(position.avg_cost, 4),
                "cost": round(position.cost, 4),
            }
            for position in market_positions
        ]
        out["market_concentration_pct"] = round(
            market_notional / total_open_notional * 100 if total_open_notional > 0 else 0.0,
            2,
        )
    except Exception as exc:
        logger.debug("assistant exposure lookup failed for %s: %s", slug, exc)
    return out


async def _enrich_analyze_context(
    slug: str, ctx: dict[str, Any], db: AsyncSession
) -> dict[str, Any]:
    """Pull real price/volume/24h move/brief/drivers for analyze intent.

    Every figure comes from an existing read-only store. Missing data is left
    absent (never fabricated). Does NOT import OrderBookService / RiskService.
    """
    out = dict(ctx)

    # M1: use persisted predictions when present; otherwise invoke the exact
    # prediction path used by /markets/{slug}/prediction behind a <=60s cache.
    # An unscorable result has an explicit reason instead of a fabricated value.
    out.update(await _prediction_context_for_analyze(slug, db))

    # Market row: title, volume, latest YES price (via MarketService subquery).
    try:
        from app.services.market_service import MarketService

        market = await MarketService(db).get_public_market_by_slug(slug)
        if market is not None:
            out["title"] = market.title
            out["volume"] = int(market.volume or 0)
            if market.yes_price is not None:
                out["market_price"] = round(float(market.yes_price), 4)
    except Exception as exc:
        logger.debug("analyze market lookup failed for %s: %s", slug, exc)

    # Catalog implied as fallback market price when DB price absent.
    if out.get("market_price") is None:
        try:
            from app.api.v1.market_prediction import _implied_prob_from_catalog
            from app.services.market_service import CATALOG_SLUGS

            if slug in CATALOG_SLUGS:
                out["market_price"] = round(_implied_prob_from_catalog(slug), 4)
        except Exception:
            pass

    # 24h move from OddsSnapshot (latest vs price at/before 24h cutoff).
    try:
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=24)
        latest = await db.scalar(
            select(OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == slug)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        older = await db.scalar(
            select(OddsSnapshot.implied_yes)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at <= cutoff,
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        if latest is not None:
            latest_f = round(float(latest), 4)
            out.setdefault("market_price", latest_f)
            if older is not None:
                older_f = round(float(older), 4)
                out["price_24h_ago"] = older_f
                out["move_24h"] = round(latest_f - older_f, 4)
    except Exception as exc:
        logger.debug("analyze 24h move failed for %s: %s", slug, exc)

    # Latest analyst brief headline (omit if none).
    try:
        headline = await db.scalar(
            select(AnalystBrief.headline)
            .where(AnalystBrief.market_slug == slug, AnalystBrief.kind == "brief")
            .order_by(AnalystBrief.created_at.desc())
            .limit(1)
        )
        if headline:
            out["brief_headline"] = str(headline)
    except Exception as exc:
        logger.debug("analyze brief lookup failed for %s: %s", slug, exc)

    # Drivers: model-vs-market gap + recent alert-family signals (read-only).
    drivers: list[dict[str, Any]] = []
    model_p = out.get("model_prob")
    market_p = out.get("market_price")
    if model_p is not None and market_p is not None:
        gap = round(float(model_p) - float(market_p), 4)
        drivers.append(
            {
                "label": "Model vs market gap",
                "direction": _lean_label(float(model_p), float(market_p)),
                "note": (
                    f"Model {float(model_p):.1%} vs market {float(market_p):.1%} "
                    f"({gap:+.1%})."
                ),
            }
        )
    if out.get("news_headline"):
        sentiment = out.get("news_sentiment")
        direction = "neutral"
        if isinstance(sentiment, (int, float)):
            direction = (
                "favors YES"
                if sentiment > 0.1
                else "favors NO"
                if sentiment < -0.1
                else "neutral"
            )
        drivers.append(
            {
                "label": out["news_headline"],
                "direction": direction,
                "note": "news signal",
            }
        )
    try:
        from app.api.v1.alerts_feed import _build_alert_feed

        feed = await _build_alert_feed(
            db, effective_slugs=[slug], scope="explicit", since=None, limit=3
        )
        signal_counts: dict[tuple[str, str, str], int] = {}
        signal_order: list[tuple[str, str, str]] = []
        for item in feed.items:
            citation = item.citation.model_dump()
            payload = dict(item.payload or {})
            human = _humanize_signal_type(item.signal_type)
            label = citation.get("headline") or human
            payload_dir = _signal_payload_direction(payload)
            if payload_dir == "UP":
                direction = "favors YES"
            elif payload_dir == "DOWN":
                direction = "favors NO"
            else:
                direction = _lean_label(
                    citation.get("model_p"), citation.get("market_p")
                )
            magnitude = _signal_magnitude_label(payload, payload_dir)
            note = f"{human} signal" + (f", {magnitude}" if magnitude else "")
            key = (str(label), direction, note)
            if key not in signal_counts:
                signal_order.append(key)
            signal_counts[key] = signal_counts.get(key, 0) + 1
        for label, direction, note in signal_order:
            count = signal_counts[(label, direction, note)]
            drivers.append(
                {
                    "label": f"{count}x {label}" if count > 1 else label,
                    "direction": direction,
                    "note": note,
                }
            )
    except Exception as exc:
        logger.debug("analyze signal drivers failed for %s: %s", slug, exc)

    if drivers:
        out["drivers"] = drivers[:5]

    # Recompute edge from enriched market price when model_prob exists.
    if out.get("model_prob") is not None and out.get("market_price") is not None:
        out["edge"] = round(float(out["model_prob"]) - float(out["market_price"]), 4)

    return out


def _build_analyze_reply(
    ctx: dict[str, Any],
    market_slug: str | None,
) -> tuple[str, list[CitationChip], list[str]]:
    """Deterministic paper-trade analysis from real service figures only."""
    citations: list[CitationChip] = []
    tools_used: list[str] = ["get_features"]
    parts: list[str] = []

    title = ctx.get("title") or market_slug or "this market"
    parts.append(f"Paper-trade analysis for {title}.")

    # Price + volume
    market_price = ctx.get("market_price")
    volume = ctx.get("volume")
    price_bits: list[str] = []
    if market_price is not None:
        tools_used.append("get_odds")
        cents = round(float(market_price) * 100)
        price_bits.append(f"YES ~{cents}¢ ({float(market_price):.1%})")
        citations.append(CitationChip(source="odds", label="Market price"))
    if volume is not None:
        price_bits.append(f"volume ${int(volume):,}")
    if price_bits:
        parts.append("Market: " + ", ".join(price_bits) + ".")
    else:
        parts.append("Market price/volume: not available for this slug.")

    # 24h move — only when both sides exist
    move = ctx.get("move_24h")
    price_24h = ctx.get("price_24h_ago")
    if move is not None and market_price is not None and price_24h is not None:
        parts.append(
            f"24h move: {float(move):+.1%} "
            f"(from {float(price_24h):.1%} → {float(market_price):.1%})."
        )
    else:
        parts.append("24h move: no snapshot pair available — omitted.")

    # Model vs market
    model_prob = ctx.get("model_prob")
    edge = ctx.get("edge")
    if model_prob is not None and market_price is not None:
        edge_s = f"{float(edge):+.1%}" if edge is not None else "n/a"
        parts.append(
            f"Model vs market: model {float(model_prob):.1%} vs market "
            f"{float(market_price):.1%} (edge {edge_s})."
        )
        citations.append(CitationChip(source="features", label="Model features"))
    elif model_prob is not None:
        parts.append(f"Model probability: {float(model_prob):.1%} (market price absent).")
        citations.append(CitationChip(source="features", label="Model features"))
    else:
        reason = ctx.get("unscorable_reason")
        if reason:
            parts.append(f"Model probability: not available — {reason}.")
        else:
            parts.append("Model probability: not available — omitted.")

    reason = ctx.get("forecast_reason")
    if reason:
        parts.append(f"Model gate: {reason}.")

    # Drivers
    drivers = ctx.get("drivers") or []
    if drivers:
        driver_lines = []
        for d in drivers[:5]:
            driver_lines.append(
                f"- {d.get('label', 'driver')} ({d.get('direction', 'neutral')}): "
                f"{d.get('note', '')}".rstrip()
            )
        parts.append("Drivers:\n" + "\n".join(driver_lines))
        citations.append(CitationChip(source="features", label="Forecast drivers"))
    else:
        parts.append("Drivers: none available for this market — omitted.")

    # Analyst brief
    brief = ctx.get("brief_headline")
    if brief:
        tools_used.append("get_briefs")
        parts.append(f'Latest analyst brief: "{brief}".')
        citations.append(CitationChip(source="briefs", label="Analyst brief"))

    # Honest uncertainty + paper-only
    parts.append(
        "Uncertainty: forecasts are provisional; absent fields above were omitted, "
        "not invented. Numbers come only from existing market/model/signal services."
    )
    parts.append(f"{ANALYSIS_ONLY_BANNER} {PAPER_ONLY_DISCLAIMER}")

    # De-dupe tools while preserving order
    seen: set[str] = set()
    ordered_tools: list[str] = []
    for t in tools_used:
        if t not in seen:
            seen.add(t)
            ordered_tools.append(t)

    return "\n".join(parts), citations, ordered_tools


def _build_bear_case_reply(
    ctx: dict[str, Any], market_slug: str | None
) -> tuple[str, list[CitationChip], list[str]]:
    """Format bear-case facts only when the source data supplied them."""
    title = ctx.get("title") or market_slug or "this market"
    parts = [f"Bear-case data for {title}."]
    citations = [CitationChip(source="features", label="Model and signal data")]
    tools_used = ["get_features"]

    drivers = ctx.get("negative_drivers") or []
    if drivers:
        parts.append(
            "Top negative drivers:\n"
            + "\n".join(
                f"- {driver.get('label', 'driver')}: {driver.get('note', '')}".rstrip()
                for driver in drivers[:3]
            )
        )
    else:
        parts.append("Top negative drivers: none in the available signal data — omitted.")

    move = _finite(ctx.get("move_24h"))
    if move is not None and move < 0:
        parts.append(f"Recent adverse YES move: {move:+.1%} over the stored 24h comparison.")
        tools_used.append("get_odds")
        citations.append(CitationChip(source="odds", label="24h odds snapshots"))
    elif move is not None:
        parts.append("Recent adverse YES move: none in the stored 24h comparison.")
    else:
        parts.append("Recent adverse YES move: no snapshot pair available — omitted.")

    percentile = _finite(ctx.get("volume_percentile"))
    volume = _finite(ctx.get("volume"))
    if percentile is not None and volume is not None:
        parts.append(
            f"Liquidity proxy: ${volume:,.0f} catalog volume, percentile {percentile:.0f}. "
            "Lower percentiles indicate less catalog volume."
        )
        citations.append(CitationChip(source="odds", label="Market catalog volume"))
    else:
        parts.append("Liquidity proxy: catalog percentile unavailable — omitted.")

    hours_to_close = _finite(ctx.get("hours_to_close"))
    if hours_to_close is None:
        parts.append("Time to close: no lock time is stored — omitted.")
    elif hours_to_close >= 0:
        parts.append(f"Time to close: {hours_to_close:.1f} hours until the stored lock time.")
    else:
        parts.append(f"Time to close: stored lock time passed {abs(hours_to_close):.1f} hours ago.")

    parts.append(f"{ANALYSIS_ONLY_BANNER} {PAPER_ONLY_DISCLAIMER}")
    return "\n".join(parts), citations, list(dict.fromkeys(tools_used))


def _build_market_exposure_reply(
    ctx: dict[str, Any], market_slug: str | None
) -> tuple[str, list[CitationChip], list[str]]:
    """Describe authenticated, cost-basis exposure math without advice language."""
    if not ctx.get("exposure_authenticated"):
        return (
            "Sign in to view this market's paper position and portfolio concentration. "
            f"{ANALYSIS_ONLY_BANNER} {PAPER_ONLY_DISCLAIMER}",
            [CitationChip(source="exposure", label="Portfolio exposure")],
            ["get_exposure"],
        )

    title = ctx.get("title") or market_slug or "this market"
    positions = ctx.get("market_positions") or []
    parts = [f"Paper exposure for {title}."]
    if positions:
        for position in positions:
            outcome = str(position.get("outcome", "")).upper()
            shares = _finite(position.get("shares")) or 0.0
            avg_cost = _finite(position.get("avg_cost")) or 0.0
            cost = _finite(position.get("cost")) or 0.0
            opposite = "NO" if outcome == "YES" else "YES"
            parts.append(
                f"Current {outcome} position: {shares:g} shares at ${avg_cost:.2f} average "
                f"cost (cost basis ${cost:.2f}); a {opposite} resolution changes paper "
                f"balance by −${cost:.2f} for this position."
            )
    else:
        parts.append("Current position in this market: none among open paper positions.")

    concentration = _finite(ctx.get("market_concentration_pct"))
    if concentration is not None:
        parts.append(
            f"Portfolio concentration: this market is {concentration:.1f}% of open "
            "cost-basis notional."
        )
    else:
        parts.append("Portfolio concentration: unavailable — omitted.")
    parts.append(f"{ANALYSIS_ONLY_BANNER} {PAPER_ONLY_DISCLAIMER}")
    return "\n".join(parts), [CitationChip(source="exposure", label="Paper positions")], ["get_exposure"]


def _build_profile_snippet(profile: dict[str, Any] | None) -> str:
    """Return a short context snippet for the profile (used in deterministic fallback).

    Returns empty string if no profile or has_data is False.
    The NUMBERS come from the deterministic service; this function only formats them.
    """
    if not profile or not profile.get("has_data"):
        return ""
    parts: list[str] = []
    cats = profile.get("favorite_categories", [])
    if cats:
        parts.append(f"Your top categories: {', '.join(cats[:2])}.")
    avg_size_pct = profile.get("avg_size_pct_bankroll", 0.0)
    if avg_size_pct > 0:
        parts.append(f"Typical position: {avg_size_pct:.1f}% of bankroll.")
    streak = profile.get("current_streak", 0)
    if streak <= -2:
        parts.append(f"You are on a {abs(streak)}-trade losing streak.")
    if profile.get("sizes_up_after_losses"):
        mult = profile.get("tilt_multiplier", 1.0)
        parts.append(f"You tend to size up {mult:.1f}x after losses (tilt detected).")
    return " ".join(parts)


def _build_deterministic_reply(
    message: str,
    ctx: dict[str, Any],
    market_slug: str | None,
    trader_profile: dict[str, Any] | None = None,
) -> tuple[str, list[CitationChip], list[str]]:
    """Deterministic fallback answer when no LLM key is configured.

    Returns (reply, citations, tools_used).
    """
    msg_lower = message.lower()
    citations: list[CitationChip] = []
    tools_used: list[str] = []

    # ── AI Analyze / deep-dive (market-card seed prompts) ────────────────────
    if _is_analyze_intent(message):
        return _build_analyze_reply(ctx, market_slug)

    # ── bear case ────────────────────────────────────────────────────────────
    if _is_bear_intent(message):
        return _build_bear_case_reply(ctx, market_slug)

    # ── odds / price movement ────────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("odds", "price", "move", "why did")):
        tools_used.append("get_odds")
        if market_slug and ctx:
            headline = ctx.get("news_headline", "")
            sentiment = ctx.get("news_sentiment")
            edge = ctx.get("edge")
            model_prob = ctx.get("model_prob")

            parts: list[str] = []
            if model_prob is not None:
                parts.append(f"The model currently prices this market at {model_prob:.1%}.")
            if sentiment is not None:
                direction = (
                    "bullish" if sentiment > 0.1 else "bearish" if sentiment < -0.1 else "neutral"
                )
                parts.append(f"News sentiment is {direction} ({sentiment:+.2f}).")
                if headline:
                    parts.append(f'Recent headline: "{headline}".')
                    citations.append(CitationChip(source="news", label="News signal"))
            if edge is not None:
                parts.append(
                    f"Current edge vs market: {edge:+.3f} "
                    f"({'positive — potential opportunity' if edge > 0.02 else 'weak or negative'})."
                )
            if parts:
                reply = " ".join(parts)
            else:
                reply = (
                    "No live market data is available for this market right now. "
                    "Price movements may reflect news events or whale activity — "
                    "check the activity feed for recent signals."
                )
        else:
            reply = (
                "Odds can shift due to: (1) new information priced in by informed traders, "
                "(2) whale-position changes detected by the tracker, "
                "(3) news sentiment shifts, or (4) instability signals. "
                "Select a specific market to see its current signals."
            )
        return reply, citations, tools_used

    # ── exposure / portfolio ─────────────────────────────────────────────────
    if _is_exposure_intent(message):
        if market_slug:
            return _build_market_exposure_reply(ctx, market_slug)
        tools_used.append("get_exposure")
        profile_snippet = _build_profile_snippet(trader_profile)
        base_reply = (
            "Your portfolio exposure is summarised in the Exposure panel above. "
            "Concentration risk appears when >40 % of your open notional is in "
            "one correlated underlier (e.g. the same team across multiple markets). "
            "This is a paper-trading simulation — no real funds are at risk."
        )
        if profile_snippet:
            tools_used.append("get_trader_profile")
            reply = base_reply + " " + profile_snippet
            citations.append(CitationChip(source="trader_profile", label="Your trading profile"))
        else:
            reply = base_reply
        citations.append(CitationChip(source="exposure", label="Portfolio exposure"))
        return reply, citations, tools_used

    # ── briefs / analyst notes ───────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("brief", "analyst", "note", "report", "research")):
        tools_used.append("get_briefs")
        reply = (
            "Analyst briefs are generated automatically when the alignment scorer "
            "fires (3 independent layers: price-jump, whale-delta, news-lag). "
            "Each brief includes a deterministic, machine-checkable claim and "
            "at least one citation. You can read recent briefs in the Research tab."
        )
        citations.append(CitationChip(source="briefs", label="Analyst briefs"))
        return reply, citations, tools_used

    # ── agent trace ──────────────────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("trace", "model", "decision", "why bet", "reasoning")):
        tools_used.append("get_agent_trace")
        if market_slug and ctx.get("model_prob") is not None:
            model_prob = ctx["model_prob"]
            reason = ctx.get("forecast_reason", "see full trace")
            reply = (
                f"The agent graph runs 5 nodes: data → news → prediction → risk → reasoning. "
                f"For this market the model outputs {model_prob:.1%} probability. "
                f"Gate result: {reason}. "
                "Expand the Rationale Trace in the Decision card for the full per-step breakdown."
            )
        else:
            reply = (
                "The agent graph (data → news → prediction → risk → reasoning) is visible "
                "in the Decision card for any open market. Expand the rationale trace to see "
                "exactly which inputs drove the model's probability and edge estimate."
            )
        citations.append(CitationChip(source="agent_trace", label="Agent trace"))
        return reply, citations, tools_used

    # ── fallback — unrecognized intent only ──────────────────────────────────
    tools_used.append("get_features")
    profile_snippet = _build_profile_snippet(trader_profile)
    base_fallback = (
        f"{_MENU_MARKER} odds movement analysis, portfolio exposure, bear-case "
        "risk factors, analyst briefs, and agent-reasoning traces. "
        "Try asking: 'Why did odds move today?', 'What's my overall exposure?', "
        "or 'What's the bear case?'. "
        f"{ANALYSIS_ONLY_BANNER}"
    )
    if profile_snippet:
        tools_used.append("get_trader_profile")
        reply = base_fallback + " " + profile_snippet
    else:
        reply = base_fallback
    return reply, citations, tools_used


async def _llm_reply(
    message: str,
    ctx: dict[str, Any],
    history: list[ChatMessage],
    market_slug: str | None,
    trader_profile: dict[str, Any] | None = None,
) -> tuple[str, list[CitationChip], list[str]]:
    """Attempt an LLM reply; fall back to deterministic on any error."""
    settings = get_settings()
    from app.llm.provider import resolve_routed_endpoint

    _, api_key = resolve_routed_endpoint(settings, settings.llm_route_chat)
    if not api_key:
        return _build_deterministic_reply(message, ctx, market_slug, trader_profile)

    try:
        from app.llm.provider import resolve_routed_client

        client, chat_model = resolve_routed_client(
            settings, settings.llm_route_chat,
            use_case_model=settings.llm_model_chat,
        )

        system_parts: list[str] = [
            "You are AlphaEdge Analyst — a read-only market analysis assistant.",
            ANALYSIS_ONLY_BANNER,
            "You CANNOT place trades, submit orders, or reference any order-execution tool.",
            "You answer using only the context provided below.",
            "Keep answers concise (≤300 words). Cite evidence from the context.",
            "IMPORTANT: The user's trading profile numbers come from deterministic math "
            "over their paper-trade history. You may narrate these numbers but MUST NOT "
            "invent or modify any statistics.",
        ]
        if ctx:
            system_parts.append(f"Market context: {ctx}")
        # U13 — inject profile as read-only context (narrate, never fabricate)
        if trader_profile and trader_profile.get("has_data"):
            profile_snippet = _build_profile_snippet(trader_profile)
            if profile_snippet:
                system_parts.append(f"User trading profile (derived from paper history): {profile_snippet}")

        system_prompt = "\n".join(system_parts)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for h in history[-10:]:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model=chat_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=400,
            temperature=0.3,
        )
        reply_text = response.choices[0].message.content or ""
        # Ensure banner is always present
        if ANALYSIS_ONLY_BANNER.lower() not in reply_text.lower():
            reply_text = reply_text.strip() + f"\n\n_{ANALYSIS_ONLY_BANNER}_"

        tools_used = ["get_features"]
        if ctx.get("news_headline"):
            tools_used.append("get_odds")
        citations: list[CitationChip] = []
        if ctx.get("news_headline"):
            citations.append(CitationChip(source="news", label="News signal"))

        return reply_text, citations, tools_used

    except Exception as exc:
        logger.warning("LLM call failed, using deterministic fallback: %s", exc)
        return _build_deterministic_reply(message, ctx, market_slug, trader_profile)


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    body: AssistantChatRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantChatResponse:
    """Analysis-only chat.  Cannot emit order intents.

    Uses read-only context: news signals, model features, exposure (U04),
    briefs (T12), agent trace (U03). Works with no LLM key via deterministic
    fallback.

    Auth: optional. A valid bearer token authenticates the caller and bypasses
    the per-IP limit. Anonymous calls (no token) are rate-limited per IP
    (ASSISTANT_ANON_RATE_PER_MIN, default 10/min) so the public demo keeps
    working while preventing unbounded abuse.
    """
    if current_user is None:
        ip = _client_ip(request)
        limit = get_settings().assistant_anon_rate_per_min
        if not _anon_allowed(ip, limit):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Rate limit exceeded for anonymous assistant chat. "
                    "Sign in to continue."
                ),
            )

    market_slug = body.market_slug
    ctx: dict[str, Any] = {}

    if market_slug:
        try:
            ctx = _gather_market_context(market_slug)
        except Exception as exc:
            logger.warning("Context assembly failed for %s: %s", market_slug, exc)
            ctx = {}
        if _is_analyze_intent(body.message) or _is_bear_intent(body.message):
            try:
                ctx = await _enrich_analyze_context(market_slug, ctx, db)
            except Exception as exc:
                logger.warning("Assistant market enrich failed for %s: %s", market_slug, exc)
        if _is_bear_intent(body.message):
            try:
                ctx = await _enrich_bear_case_context(market_slug, ctx, db)
            except Exception as exc:
                logger.warning("Bear-case enrich failed for %s: %s", market_slug, exc)
        if _is_exposure_intent(body.message) and current_user is not None:
            try:
                ctx = await _enrich_exposure_context(market_slug, ctx, current_user, db)
            except Exception as exc:
                logger.warning("Exposure enrich failed for %s: %s", market_slug, exc)

    reply, citations, tools_used = await _llm_reply(
        body.message, ctx, body.history, market_slug,
        trader_profile=body.trader_profile_context,
    )

    return AssistantChatResponse(
        reply=reply,
        citations=citations,
        tools_used=tools_used,
        paper_trading_only=True,
        analysis_only_banner=ANALYSIS_ONLY_BANNER,
    )
