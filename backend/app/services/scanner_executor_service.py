"""Checkpointed scanner executor over mirrored markets (research-only).

Reuses the same read-only service calls as ``terminal_research_service``.
Never creates paper orders or calls RiskService / OrderBookService.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market_candles import _build_market_candles
from app.db.models import Market, MarketStatus, Scanner, ScannerRun
from app.services.forecast_service import ForecastService
from app.services.market_service import MarketService
from app.services.whale_flow_service import WhaleFlowService
from app.signals.news_signal import fetch_news_signal
from app.signals.sentiment_trend import load_sentiment_trend

_SIGNAL_TYPES = frozenset({"WHALE_FLOW", "PRICE_TREND", "NEWS_SENTIMENT", "MODEL_EDGE"})


def _category_match(market: Market, categories: list[str]) -> bool:
    if not categories:
        return True
    cat = (market.category or "").lower()
    slug = (market.slug or "").lower()
    title = (market.title or "").lower()
    for wanted in categories:
        w = wanted.lower().strip()
        if not w:
            continue
        if w == cat or w in cat or w in slug or w in title:
            return True
    return False


async def _load_universe(db: AsyncSession, spec: dict[str, Any]) -> list[Market]:
    universe = spec.get("universe") or {}
    categories = list(universe.get("categories") or [])
    min_vol = int(universe.get("minimum_volume") or 0)
    limit = int(spec.get("limit") or 20)

    rows = (
        await db.scalars(
            select(Market)
            .where(Market.status == MarketStatus.OPEN)
            .order_by(Market.volume.desc(), Market.created_at.desc())
        )
    ).all()
    filtered = [
        m
        for m in rows
        if _category_match(m, categories) and int(m.volume or 0) >= min_vol
    ]
    return list(filtered[: max(limit, 0)])


def _direction_from_pressure(pressure: float) -> str | None:
    if pressure > 0.05:
        return "up"
    if pressure < -0.05:
        return "down"
    return None


def _direction_from_sentiment(score: float) -> str | None:
    if score > 0.05:
        return "up"
    if score < -0.05:
        return "down"
    return None


def _candidate_directions(cand: dict[str, Any]) -> list[str]:
    reads = cand.get("reads") or {}
    dirs: list[str] = []
    whale = reads.get("WHALE_FLOW") or {}
    if whale.get("direction"):
        dirs.append(str(whale["direction"]))
    trend = reads.get("PRICE_TREND") or {}
    if trend.get("direction"):
        dirs.append(str(trend["direction"]))
    news = reads.get("NEWS_SENTIMENT") or {}
    if news.get("direction"):
        dirs.append(str(news["direction"]))
    edge = reads.get("MODEL_EDGE") or {}
    if edge.get("direction"):
        dirs.append(str(edge["direction"]))
    return dirs


def _is_aligned(cand: dict[str, Any]) -> bool:
    dirs = _candidate_directions(cand)
    if not dirs:
        return False
    return len(set(dirs)) == 1


async def _step_whale_flow(db: AsyncSession, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    svc = WhaleFlowService(db)
    annotated: list[dict[str, Any]] = []
    for cand in candidates:
        pressure = await svc.pressure_for(cand["market_slug"])
        read = {
            "pressure": float(pressure.pressure),
            "event_count": int(pressure.event_count),
            "net_notional": float(pressure.net_notional),
            "total_notional": float(pressure.total_notional),
            "direction": _direction_from_pressure(float(pressure.pressure)),
            "flow_score": abs(float(pressure.net_notional))
            + abs(float(pressure.pressure)) * 1000.0,
        }
        cand = dict(cand)
        reads = dict(cand.get("reads") or {})
        reads["WHALE_FLOW"] = read
        cand["reads"] = reads
        annotated.append(cand)
    annotated.sort(
        key=lambda c: float((c.get("reads") or {}).get("WHALE_FLOW", {}).get("flow_score") or 0.0),
        reverse=True,
    )
    return annotated


async def _step_price_trend(
    db: AsyncSession,
    candidates: list[dict[str, Any]],
    *,
    window_days: int,
    align_present: bool,
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for cand in candidates:
        direction = None
        change = None
        try:
            body = await _build_market_candles(cand["market_slug"], max(int(window_days), 1), db)
            candles = body.get("candles") or []
        except Exception:
            candles = []
        if len(candles) >= 2:
            first = float(candles[0].get("close") or candles[0].get("open") or 0.0)
            last = float(candles[-1].get("close") or candles[-1].get("open") or 0.0)
            change = round(last - first, 6)
            if change > 0.005:
                direction = "up"
            elif change < -0.005:
                direction = "down"
        read = {
            "window_days": int(window_days),
            "direction": direction,
            "change": change,
            "candle_count": len(candles),
        }
        cand = dict(cand)
        reads = dict(cand.get("reads") or {})
        reads["PRICE_TREND"] = read
        cand["reads"] = reads
        annotated.append(cand)

    if align_present:
        # Drop candidates whose price direction conflicts with earlier signal dirs.
        kept: list[dict[str, Any]] = []
        for cand in annotated:
            trend_dir = (cand.get("reads") or {}).get("PRICE_TREND", {}).get("direction")
            if trend_dir is None:
                kept.append(cand)
                continue
            prior = []
            for key in ("WHALE_FLOW", "NEWS_SENTIMENT", "MODEL_EDGE"):
                d = (cand.get("reads") or {}).get(key, {}).get("direction")
                if d:
                    prior.append(d)
            if prior and any(d != trend_dir for d in prior):
                continue
            kept.append(cand)
        return kept
    return annotated


async def _step_news_sentiment(
    db: AsyncSession, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for cand in candidates:
        news = await fetch_news_signal(cand["market_slug"])
        trend = await load_sentiment_trend(
            db, market_slug=cand["market_slug"], as_of=datetime.now(UTC)
        )
        score = None
        if news is not None:
            score = float(news.sentiment_score)
        elif trend.get("available") and trend.get("direction") is not None:
            score = float(trend["direction"])  # type: ignore[arg-type]
        read: dict[str, Any] = {
            "sentiment_score": score,
            "direction": _direction_from_sentiment(score) if score is not None else None,
            "news": None,
            "trend_available": bool(trend.get("available")),
        }
        if news is not None:
            read["news"] = {
                "headline": news.headline,
                "sentiment_score": news.sentiment_score,
                "sources_count": news.sources_count,
            }
        cand = dict(cand)
        reads = dict(cand.get("reads") or {})
        reads["NEWS_SENTIMENT"] = read
        cand["reads"] = reads
        annotated.append(cand)
    return annotated


async def _step_model_edge(db: AsyncSession, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    mkt_svc = MarketService(db)
    for cand in candidates:
        public = await mkt_svc.get_public_market_by_slug(cand["market_slug"])
        market_p = float(public.yes_price) if public and public.yes_price is not None else None
        implied = market_p if market_p is not None else 0.5
        forecast = ForecastService.predict(cand["market_slug"], implied_yes=implied)
        model_p = None
        edge = None
        direction = None
        if forecast is not None:
            model_p = float(forecast.model_prob)
            if market_p is not None:
                edge = round(model_p - market_p, 4)
                if edge > 0.01:
                    direction = "up"
                elif edge < -0.01:
                    direction = "down"
        read = {
            "model_prob": model_p,
            "market_prob": market_p,
            "edge": edge,
            "direction": direction,
        }
        cand = dict(cand)
        reads = dict(cand.get("reads") or {})
        reads["MODEL_EDGE"] = read
        cand["reads"] = reads
        annotated.append(cand)
    return annotated


def _step_direction_alignment(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for cand in candidates:
        cand = dict(cand)
        aligned = _is_aligned(cand)
        cand["aligned"] = aligned
        reads = dict(cand.get("reads") or {})
        reads["DIRECTION_ALIGNMENT"] = {"aligned": aligned}
        cand["reads"] = reads
        dirs = _candidate_directions(cand)
        if dirs and not aligned:
            continue
        kept.append(cand)
    return kept


async def _run_step(
    db: AsyncSession,
    step: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    align_present: bool,
) -> list[dict[str, Any]]:
    stype = str(step.get("type") or "").upper()
    if stype == "WHALE_FLOW":
        return await _step_whale_flow(db, candidates)
    if stype == "PRICE_TREND":
        window = int(step.get("window_days") or 7)
        return await _step_price_trend(
            db, candidates, window_days=window, align_present=align_present
        )
    if stype == "NEWS_SENTIMENT":
        return await _step_news_sentiment(db, candidates)
    if stype == "MODEL_EDGE":
        return await _step_model_edge(db, candidates)
    if stype == "DIRECTION_ALIGNMENT":
        return _step_direction_alignment(candidates)
    # Unknown step types are no-ops (still checkpointed by caller).
    return candidates


async def run_scanner(db: AsyncSession, scanner: Scanner) -> ScannerRun:
    """Execute ``scanner.spec`` steps with per-node checkpoints. Research only."""
    run = ScannerRun(
        scanner_id=scanner.id,
        status="running",
        started_at=datetime.now(UTC),
        checkpoint=None,
        result=None,
        error=None,
    )
    db.add(run)
    await db.flush()

    try:
        spec = dict(scanner.spec or {})
        steps = list(spec.get("steps") or [])
        align_present = any(
            str(s.get("type") or "").upper() == "DIRECTION_ALIGNMENT" for s in steps
        )

        markets = await _load_universe(db, spec)
        candidates: list[dict[str, Any]] = [
            {
                "market_slug": m.slug,
                "title": m.title,
                "reads": {},
                "aligned": False,
            }
            for m in markets
        ]
        universe_count = len(candidates)

        if universe_count == 0:
            run.status = "empty"
            run.finished_at = datetime.now(UTC)
            run.result = {
                "candidates": [],
                "top_pick": None,
                "counts": {"universe": 0, "candidates": 0, "aligned": 0},
            }
            await db.flush()
            await db.refresh(run)
            return run

        for index, step in enumerate(steps):
            candidates = await _run_step(
                db, step, candidates, align_present=align_present
            )
            run.checkpoint = {"node": index}
            await db.flush()

        # Final alignment flag for candidates that never hit DIRECTION_ALIGNMENT.
        for cand in candidates:
            if "aligned" not in cand or not align_present:
                cand["aligned"] = _is_aligned(cand)

        aligned = [c for c in candidates if c.get("aligned")]
        top_pick = aligned[0] if aligned else None
        run.result = {
            "candidates": candidates,
            "top_pick": top_pick,
            "counts": {
                "universe": universe_count,
                "candidates": len(candidates),
                "aligned": len(aligned),
            },
        }
        run.status = "empty" if not candidates else "completed"
        run.finished_at = datetime.now(UTC)
        await db.flush()

        # C6: surface fired runs on the signals/toast feed (cooldown-gated).
        try:
            from app.services.scanner_alert_service import record_scanner_fired_alert

            await record_scanner_fired_alert(db, scanner, run)
        except Exception:  # noqa: BLE001 — alert failure must not fail the run
            pass

        await db.refresh(run)
        return run
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)[:500]
        run.finished_at = datetime.now(UTC)
        # checkpoint preserved as last successful node
        await db.flush()
        await db.refresh(run)
        return run
