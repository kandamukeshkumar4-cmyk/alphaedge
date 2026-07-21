"""Read-only research planning and execution for Terminal sessions.

Deterministic step executor over existing market/signal/forecast services.
No LLM calls, no order submission — every payload comes from a real service
or the step is persisted as status="empty" with payload={}.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts_feed import _build_alert_feed
from app.api.v1.market_candles import _build_market_candles
from app.db.models import Market, ResearchSession, ResearchStep
from app.services.forecast_service import ForecastService
from app.services.market_service import MarketService
from app.services.terminal_scoreboard_service import build_scoreboard
from app.services.venue_gap_service import VenueGapService
from app.services.whale_flow_service import WhaleFlowService
from app.signals.news_signal import fetch_news_signal
from app.signals.sentiment_trend import load_sentiment_trend

_ALLOWED_KINDS = frozenset({"table", "chart", "text"})


def plan_research(question: str) -> list[dict[str, str]]:
    """Rule-based plan from the question (keyword routing, no LLM).

    Core evidence steps are always scheduled. Optional whale/venue is decided
    at execution time from live signal availability, not invented here.
    """
    q = (question or "").lower()
    # Keyword hints only affect ordering preference; required steps stay present.
    prefer_model = any(k in q for k in ("model", "edge", "forecast", "predict"))
    prefer_news = any(k in q for k in ("news", "sentiment", "headline"))
    steps: list[dict[str, str]] = [
        {"title": "Market snapshot", "kind": "table"},
        {"title": "Price history", "kind": "chart"},
        {"title": "Whale & venue flow", "kind": "table"},  # may be skipped if no signals
        {"title": "News & sentiment", "kind": "table"},
        {"title": "Model vs market", "kind": "table"},
    ]
    if prefer_model:
        steps = [steps[0], steps[1], steps[4], steps[2], steps[3]]
    elif prefer_news:
        steps = [steps[0], steps[1], steps[3], steps[2], steps[4]]
    return steps


def _cite(source: str, label: str) -> dict[str, str]:
    return {"source": source, "label": label}


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


async def _market_has_whale_or_venue_signals(db: AsyncSession, slug: str) -> bool:
    """True when whale pressure, venue gap, or alert-feed signals exist for slug."""
    pressure = await WhaleFlowService(db).pressure_for(slug)
    if pressure.event_count > 0:
        return True
    gap = await VenueGapService(db).gap_for_slug(slug)
    if gap is not None:
        return True
    feed = await _build_alert_feed(
        db, effective_slugs=[slug], scope="explicit", since=None, limit=5
    )
    return bool(feed.items)


async def _step_market_snapshot(
    db: AsyncSession, slug: str
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    market = await MarketService(db).get_public_market_by_slug(slug)
    if market is None:
        return {}, [], "empty"
    payload = {
        "slug": market.slug,
        "title": market.title,
        "yes_price": market.yes_price,
        "volume": market.volume,
        "status": market.status,
        "lock_at": market.lock_at.isoformat() if market.lock_at else None,
        "duration_ms": None,  # filled by caller
    }
    return (
        payload,
        [_cite("market_service", "get_public_market_by_slug")],
        "completed",
    )


async def _step_price_history(
    db: AsyncSession, slug: str
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    try:
        body = await _build_market_candles(slug, 90, db)
    except HTTPException:
        return {}, [], "empty"
    candles = body.get("candles") or []
    if not candles:
        return {}, [], "empty"
    series = [
        {
            "t": c.get("time"),
            "o": c.get("open"),
            "h": c.get("high"),
            "l": c.get("low"),
            "c": c.get("close"),
        }
        for c in candles
    ]
    return (
        {"series": series, "source": body.get("source"), "duration_ms": None},
        [_cite("market_candles", "GET /markets/{slug}/candles")],
        "completed",
    )


async def _step_whale_venue(
    db: AsyncSession, slug: str
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    pressure = await WhaleFlowService(db).pressure_for(slug)
    gap = await VenueGapService(db).gap_for_slug(slug)
    feed = await _build_alert_feed(
        db, effective_slugs=[slug], scope="explicit", since=None, limit=10
    )
    if pressure.event_count <= 0 and gap is None and not feed.items:
        return {}, [], "empty"
    payload: dict[str, Any] = {
        "whale": {
            "pressure": pressure.pressure,
            "event_count": pressure.event_count,
            "net_notional": pressure.net_notional,
            "total_notional": pressure.total_notional,
            "window_sec": pressure.window_sec,
        },
        "venue_gap": None,
        "signals": [
            {
                "signal_type": item.signal_type,
                "slug": item.slug,
                "created_at": item.created_at.isoformat(),
            }
            for item in feed.items
        ],
        "duration_ms": None,
    }
    if gap is not None:
        payload["venue_gap"] = {
            "pm_slug": gap.pm_slug,
            "ks_slug": gap.ks_slug,
            "pm_implied": float(gap.pm_implied),
            "ks_implied": float(gap.ks_implied),
            "gap": float(gap.gap),
            "abs_gap": float(gap.abs_gap),
            "stale": bool(gap.stale),
        }
    return (
        payload,
        [
            _cite("whale_flow_service", "pressure_for"),
            _cite("venue_gap_service", "gap_for_slug"),
            _cite("alerts_feed", "_build_alert_feed"),
        ],
        "completed",
    )


async def _step_news_sentiment(
    db: AsyncSession, slug: str
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    news = await fetch_news_signal(slug)
    trend = await load_sentiment_trend(db, market_slug=slug, as_of=datetime.now(UTC))
    if news is None and not trend.get("available"):
        return {}, [], "empty"
    payload: dict[str, Any] = {"news": None, "sentiment": dict(trend), "duration_ms": None}
    citations = [_cite("sentiment_trend", "load_sentiment_trend")]
    if news is not None:
        payload["news"] = {
            "topic": news.topic,
            "sentiment_score": news.sentiment_score,
            "volume_score": news.volume_score,
            "headline": news.headline,
            "sources_count": news.sources_count,
            "polymarket_consensus": news.polymarket_consensus,
        }
        citations.insert(0, _cite("news_signal", "fetch_news_signal"))
    return payload, citations, "completed"


async def _step_model_vs_market(
    db: AsyncSession, slug: str
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    public = await MarketService(db).get_public_market_by_slug(slug)
    market_p = float(public.yes_price) if public and public.yes_price is not None else None
    implied = market_p if market_p is not None else 0.5
    forecast = ForecastService.predict(slug, implied_yes=implied)
    if forecast is None:
        return {}, [], "empty"
    model_p = float(forecast.model_prob)
    edge = None if market_p is None else round(model_p - market_p, 4)
    return (
        {
            "model_prob": model_p,
            "market_prob": market_p,
            "edge": edge,
            "clv_gate_passed": forecast.clv_gate_passed,
            "provisional": forecast.provisional,
            "duration_ms": None,
        },
        [_cite("forecast_service", "ForecastService.predict")],
        "completed",
    )


_STEP_RUNNERS = {
    "Market snapshot": _step_market_snapshot,
    "Price history": _step_price_history,
    "Whale & venue flow": _step_whale_venue,
    "News & sentiment": _step_news_sentiment,
    "Model vs market": _step_model_vs_market,
}


async def execute_session(db: AsyncSession, session: ResearchSession) -> list[ResearchStep]:
    """Execute the deterministic research plan and persist ResearchStep rows."""
    if not session.market_slug:
        raise ValueError("A market_slug is required to execute terminal research")

    market = await db.scalar(select(Market).where(Market.slug == session.market_slug))
    if market is None:
        raise ValueError("Market not found")

    session.status = "running"
    await db.execute(delete(ResearchStep).where(ResearchStep.session_id == session.id))

    planned = plan_research(session.question)
    include_whale = await _market_has_whale_or_venue_signals(db, session.market_slug)

    steps: list[ResearchStep] = []
    sequence = 0
    for item in planned:
        title = item["title"]
        kind = item["kind"]
        if kind not in _ALLOWED_KINDS:
            continue
        if title == "Whale & venue flow" and not include_whale:
            continue

        runner = _STEP_RUNNERS.get(title)
        if runner is None:
            continue

        sequence += 1
        started = time.perf_counter()
        payload, citations, status = await runner(db, session.market_slug)
        duration_ms = _elapsed_ms(started)

        if status == "empty" or not payload:
            saved_payload: dict[str, Any] = {}
            status = "empty"
        else:
            saved_payload = dict(payload)
            saved_payload["duration_ms"] = duration_ms

        step = ResearchStep(
            session_id=session.id,
            sequence=sequence,
            title=title,
            kind=kind,
            status=status,
            payload=saved_payload,
            citations=list(citations),
        )
        db.add(step)
        steps.append(step)

    # A3 — confluence scoreboard as the final table step.
    sequence += 1
    started = time.perf_counter()
    scoreboard = await build_scoreboard(db, market)
    duration_ms = _elapsed_ms(started)
    scoreboard_payload = dict(scoreboard)
    scoreboard_payload["duration_ms"] = duration_ms
    score_step = ResearchStep(
        session_id=session.id,
        sequence=sequence,
        title="Confluence scoreboard",
        kind="table",
        status="completed",
        payload=scoreboard_payload,
        citations=[_cite("terminal_scoreboard_service", "build_scoreboard")],
    )
    db.add(score_step)
    steps.append(score_step)

    session.status = "completed"
    session.summary = {
        "market_slug": session.market_slug,
        "steps_completed": len(steps),
        "verdict": scoreboard.get("verdict"),
        "executed_at": datetime.now(UTC).isoformat(),
        "paper_trading_only": True,
        "analysis_only": True,
    }
    await db.flush()
    for step in steps:
        await db.refresh(step)
    await db.refresh(session)
    return steps
