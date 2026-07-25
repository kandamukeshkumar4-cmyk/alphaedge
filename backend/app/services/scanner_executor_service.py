"""Checkpointed scanner executor over mirrored markets (research-only).

Reuses the same read-only service calls as ``terminal_research_service``.
Never creates paper orders or calls RiskService / OrderBookService.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market_candles import _build_market_candles
from app.db.models import Market, MarketStatus, Scanner, ScannerRun
from app.services.forecast_service import ForecastService
from app.services.market_service import MarketService
from app.services.scanner_compiler_service import (
    CLOSING_SOON_DEFAULT_HOURS,
    CROSS_VENUE_DEFAULT_MIN_GAP,
)
from app.services.scanner_heal_service import (
    classify_step_error,
    coerce_numeric_strings,
    market_slug_from_error,
    repair_action_for,
)
from app.services.venue_gap_service import VenueGapService
from app.services.whale_flow_service import WhaleFlowService
from app.signals.news_signal import fetch_news_signal
from app.signals.sentiment_trend import load_sentiment_trend

logger = logging.getLogger(__name__)

_SIGNAL_TYPES = frozenset({"WHALE_FLOW", "PRICE_TREND", "NEWS_SENTIMENT", "MODEL_EDGE"})

# loop86 F-B: pre-publish test runs cap the universe so a test can never fan out
# over the full market list.
TEST_MODE_UNIVERSE_CAP = 20
DEFAULT_MAX_EXECUTION_SECONDS = 120
DEFAULT_MAX_MARKETS = 200
CONSECUTIVE_FAILURE_ALARM = 3


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


def _max_execution_seconds(spec: dict[str, Any]) -> float:
    raw = spec.get("max_execution_seconds", DEFAULT_MAX_EXECUTION_SECONDS)
    try:
        return max(float(raw), 0.0)
    except (TypeError, ValueError):
        return float(DEFAULT_MAX_EXECUTION_SECONDS)


def _max_markets(spec: dict[str, Any]) -> int:
    raw = spec.get("max_markets", DEFAULT_MAX_MARKETS)
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return DEFAULT_MAX_MARKETS


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


async def _running_run(db: AsyncSession, scanner_id: Any) -> ScannerRun | None:
    return await db.scalar(
        select(ScannerRun)
        .where(ScannerRun.scanner_id == scanner_id, ScannerRun.status == "running")
        .order_by(ScannerRun.started_at.desc())
        .limit(1)
    )


async def _maybe_deadletter_after_failure(db: AsyncSession, scanner: Scanner) -> None:
    """After 3 consecutive failed runs, mark scanner failed + feed alarm.

    Dead-letter counting ignores ``is_test`` runs — a failing test must not trip
    the alarm.
    """
    recent = (
        await db.scalars(
            select(ScannerRun)
            .where(
                ScannerRun.scanner_id == scanner.id,
                ScannerRun.is_test.is_(False),
            )
            .order_by(ScannerRun.started_at.desc())
            .limit(CONSECUTIVE_FAILURE_ALARM)
        )
    ).all()
    if len(recent) < CONSECUTIVE_FAILURE_ALARM:
        return
    if not all(r.status == "failed" for r in recent):
        return
    already_failed = scanner.status == "failed"
    scanner.status = "failed"
    await db.flush()
    if already_failed:
        return
    try:
        from app.services.scanner_alert_service import record_scanner_failing_alert

        await record_scanner_failing_alert(db, scanner, recent[0])
    except Exception:  # noqa: BLE001 — alarm must not mask the failed run
        logger.warning("scanner failing alarm hook failed", exc_info=True)


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


async def _step_cross_venue_divergence(
    db: AsyncSession, candidates: list[dict[str, Any]], *, min_gap: float
) -> list[dict[str, Any]]:
    """Keep markets whose PM↔Kalshi mirror price gap is at least ``min_gap``.

    Mirror pairing and the gap itself come from the existing venue-gap tables
    (``venue_market_matches`` → ``venue_gaps``); no new matching logic here.
    Markets with no stored mirror are SKIPPED — absence of a pair is not
    evidence of a zero gap. Current venue prices only: no resolution data.
    """
    svc = VenueGapService(db)
    kept: list[dict[str, Any]] = []
    for cand in candidates:
        row = await svc.gap_for_slug(str(cand.get("market_slug") or ""))
        if row is None:
            continue
        abs_gap = float(row.abs_gap)
        if abs_gap < float(min_gap):
            continue
        cand = dict(cand)
        reads = dict(cand.get("reads") or {})
        reads["CROSS_VENUE_DIVERGENCE"] = {
            "pm_slug": row.pm_slug,
            "ks_slug": row.ks_slug,
            "pm_implied": float(row.pm_implied),
            "ks_implied": float(row.ks_implied),
            "gap": float(row.gap),
            "abs_gap": abs_gap,
            "min_gap": float(min_gap),
            "match_confidence": float(row.match_confidence or 0.0),
            "stale": bool(row.stale),
        }
        cand["reads"] = reads
        kept.append(cand)
    kept.sort(
        key=lambda c: float(
            (c.get("reads") or {}).get("CROSS_VENUE_DIVERGENCE", {}).get("abs_gap") or 0.0
        ),
        reverse=True,
    )
    return kept


async def _step_closing_soon(
    db: AsyncSession, candidates: list[dict[str, Any]], *, within_hours: int
) -> list[dict[str, Any]]:
    """Keep still-open markets locking within ``within_hours`` of now.

    Compares against ``datetime.now(UTC)`` only (no look-ahead). Markets with
    no lock timestamp are SKIPPED rather than treated as never-closing.
    """
    if not candidates:
        return []
    slugs = [str(c.get("market_slug") or "") for c in candidates]
    rows = (await db.scalars(select(Market).where(Market.slug.in_(slugs)))).all()
    by_slug = {m.slug: m for m in rows}

    now = datetime.now(UTC)
    horizon = now + timedelta(hours=int(within_hours))
    kept: list[dict[str, Any]] = []
    for cand in candidates:
        market = by_slug.get(str(cand.get("market_slug") or ""))
        if market is None or market.status != MarketStatus.OPEN:
            continue
        lock_at = market.lock_at
        if lock_at is None:
            continue
        if lock_at.tzinfo is None:
            lock_at = lock_at.replace(tzinfo=UTC)
        if lock_at < now or lock_at > horizon:
            continue
        hours_to_lock = (lock_at - now).total_seconds() / 3600.0
        cand = dict(cand)
        reads = dict(cand.get("reads") or {})
        reads["CLOSING_SOON"] = {
            "lock_at": lock_at.isoformat(),
            "hours_to_lock": round(hours_to_lock, 4),
            "within_hours": int(within_hours),
        }
        cand["reads"] = reads
        kept.append(cand)
    kept.sort(
        key=lambda c: float(
            (c.get("reads") or {}).get("CLOSING_SOON", {}).get("hours_to_lock") or 0.0
        )
    )
    return kept


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
    if stype == "CROSS_VENUE_DIVERGENCE":
        raw_gap = step.get("min_gap", CROSS_VENUE_DEFAULT_MIN_GAP)
        try:
            min_gap = float(raw_gap)
        except (TypeError, ValueError):
            min_gap = float(CROSS_VENUE_DEFAULT_MIN_GAP)
        return await _step_cross_venue_divergence(db, candidates, min_gap=min_gap)
    if stype == "CLOSING_SOON":
        raw_hours = step.get("within_hours", CLOSING_SOON_DEFAULT_HOURS)
        try:
            within_hours = int(raw_hours)
        except (TypeError, ValueError):
            within_hours = int(CLOSING_SOON_DEFAULT_HOURS)
        return await _step_closing_soon(db, candidates, within_hours=within_hours)
    if stype == "DIRECTION_ALIGNMENT":
        return _step_direction_alignment(candidates)
    # Unknown step types are no-ops (still checkpointed by caller).
    return candidates


async def _heal_sleep(seconds: float) -> None:
    """Awaitable sleep used by heal retries (tests monkeypatch this)."""
    await asyncio.sleep(seconds)


def _heal_jitter() -> float:
    """Jitter in [0, 1) added to rate-limit backoff."""
    return random.random()


async def _run_step_with_heal(
    db: AsyncSession,
    step: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    align_present: bool,
    node: int,
    repairs: list[dict[str, Any]],
    dropped_slugs: list[str],
) -> list[dict[str, Any]]:
    """Execute one step; on failure apply a single deterministic repair (no LLM).

    Repairs never mutate ``scanner.spec``. Applied repairs are appended to
    ``repairs`` as ``{"node", "class", "action"}`` for the run result only.
    ``unknown`` (and exhausted repairs) propagate to the caller.
    """
    context: dict[str, Any] = {
        "node": node,
        "step": step,
        "candidates": candidates,
    }

    async def _once(
        step_arg: dict[str, Any], cands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return await _run_step(db, step_arg, cands, align_present=align_present)

    try:
        return await _once(step, candidates)
    except Exception as exc:
        error_class = classify_step_error(exc, context)
        action = repair_action_for(error_class)
        if action is None:
            raise

        repair_rec = {"node": node, "class": error_class, "action": action}
        repairs.append(repair_rec)

        if error_class == "type_mismatch":
            coerced_step = coerce_numeric_strings(dict(step))
            coerced_cands = coerce_numeric_strings([dict(c) for c in candidates])
            return await _once(coerced_step, coerced_cands)

        if error_class == "missing_field":
            stype = str(step.get("type") or "").upper()
            out: list[dict[str, Any]] = []
            for cand in candidates:
                row = dict(cand)
                row["degraded"] = True
                reads = dict(row.get("reads") or {})
                if stype:
                    prev = dict(reads.get(stype) or {})
                    prev["degraded"] = True
                    prev.setdefault("value", None)
                    reads[stype] = prev
                row["reads"] = reads
                out.append(row)
            return out

        if error_class == "empty_response":
            await _heal_sleep(1.0)
            try:
                return await _once(step, candidates)
            except Exception as retry_exc:
                if classify_step_error(retry_exc, context) == "empty_response":
                    return []
                raise

        if error_class == "rate_limited":
            await _heal_sleep(2.0 + float(_heal_jitter()))
            return await _once(step, candidates)

        if error_class in ("invalid_market", "expired_market"):
            slug = market_slug_from_error(exc, context)
            kept = list(candidates)
            if slug:
                dropped_slugs.append(slug)
                slug_l = slug.lower()
                kept = [
                    c
                    for c in candidates
                    if str(c.get("market_slug") or "").lower() != slug_l
                ]
            if kept:
                try:
                    return await _once(step, kept)
                except Exception:
                    return kept
            return kept

        if error_class == "provider_transient":
            await _heal_sleep(2.0)
            return await _once(step, candidates)

        raise


def _test_mode_result_fields(scanner: Scanner, test_mode: bool) -> dict[str, Any]:
    """Result markers for pre-publish test runs (loop86 F-B).

    ``spec_version`` stamps which scanner spec version the test exercised, so
    the publish gate can require a test run for the CURRENT spec version.
    """
    if not test_mode:
        return {}
    return {"test_mode": True, "spec_version": int(scanner.version or 1)}


async def run_scanner(
    db: AsyncSession, scanner: Scanner, test_mode: bool = False
) -> ScannerRun:
    """Execute ``scanner.spec`` steps with per-node checkpoints. Research only.

    With ``test_mode=True`` the same pipeline runs, but (a) the universe is
    capped at ``min(TEST_MODE_UNIVERSE_CAP, max_markets)``, (b) the run is
    flagged ``is_test``, (c) NO alert feed rows are written and NO email is
    sent, and (d) the result JSON carries ``{"test_mode": true}``.
    """
    # Test runs bypass the idempotency skip (still respect deadline + caps).
    if not test_mode:
        existing = await _running_run(db, scanner.id)
        if existing is not None:
            return existing

    run = ScannerRun(
        scanner_id=scanner.id,
        status="running",
        started_at=datetime.now(UTC),
        checkpoint=None,
        result=None,
        error=None,
        is_test=bool(test_mode),
    )
    db.add(run)
    await db.flush()

    try:
        spec = dict(scanner.spec or {})
        steps = list(spec.get("steps") or [])
        align_present = any(
            str(s.get("type") or "").upper() == "DIRECTION_ALIGNMENT" for s in steps
        )
        max_seconds = _max_execution_seconds(spec)
        max_markets = _max_markets(spec)
        deadline = time.monotonic() + max_seconds
        # Test mode takes the tighter of the test-universe cap and max_markets.
        effective_max = (
            min(TEST_MODE_UNIVERSE_CAP, max_markets) if test_mode else max_markets
        )

        markets = await _load_universe(db, spec)
        truncated = False
        pre_cap = len(markets)
        if effective_max >= 0 and len(markets) > effective_max:
            markets = markets[:effective_max]
            truncated = True
            logger.info(
                "scanner %s universe truncated %s -> %s (max_markets)",
                scanner.id,
                pre_cap,
                effective_max,
            )

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
        repairs: list[dict[str, Any]] = []
        dropped_slugs: list[str] = []

        def _counts(*, candidates_n: int, aligned_n: int) -> dict[str, Any]:
            counts: dict[str, Any] = {
                "universe": universe_count,
                "candidates": candidates_n,
                "aligned": aligned_n,
            }
            if truncated:
                counts["truncated"] = True
                counts["truncated_from"] = pre_cap
                counts["max_markets"] = effective_max
            if dropped_slugs:
                counts["dropped"] = len(dropped_slugs)
            return counts

        def _attach_repairs(body: dict[str, Any]) -> dict[str, Any]:
            if repairs:
                body["repairs"] = list(repairs)
            return body

        if universe_count == 0:
            run.status = "empty"
            run.finished_at = datetime.now(UTC)
            run.result = _attach_repairs(
                {
                    "candidates": [],
                    "top_pick": None,
                    "counts": _counts(candidates_n=0, aligned_n=0),
                    **_test_mode_result_fields(scanner, test_mode),
                }
            )
            await db.flush()
            await db.refresh(run)
            return run

        for index, step in enumerate(steps):
            if time.monotonic() > deadline:
                run.status = "failed"
                run.error = "timeout"
                run.finished_at = datetime.now(UTC)
                run.result = _attach_repairs(
                    {
                        "candidates": candidates,
                        "top_pick": None,
                        "counts": _counts(candidates_n=len(candidates), aligned_n=0),
                        **_test_mode_result_fields(scanner, test_mode),
                    }
                )
                await db.flush()
                if not test_mode:
                    await _maybe_deadletter_after_failure(db, scanner)
                await db.refresh(run)
                return run

            try:
                candidates = await _run_step_with_heal(
                    db,
                    step,
                    candidates,
                    align_present=align_present,
                    node=index,
                    repairs=repairs,
                    dropped_slugs=dropped_slugs,
                )
            except Exception as step_exc:
                run.status = "failed"
                run.error = str(step_exc)[:500]
                run.finished_at = datetime.now(UTC)
                run.result = _attach_repairs(
                    {
                        "candidates": candidates,
                        "top_pick": None,
                        "counts": _counts(candidates_n=len(candidates), aligned_n=0),
                        **_test_mode_result_fields(scanner, test_mode),
                    }
                )
                await db.flush()
                if not test_mode:
                    await _maybe_deadletter_after_failure(db, scanner)
                await db.refresh(run)
                return run

            run.checkpoint = {"node": index}
            await db.flush()

            if time.monotonic() > deadline:
                run.status = "failed"
                run.error = "timeout"
                run.finished_at = datetime.now(UTC)
                run.result = _attach_repairs(
                    {
                        "candidates": candidates,
                        "top_pick": None,
                        "counts": _counts(candidates_n=len(candidates), aligned_n=0),
                        **_test_mode_result_fields(scanner, test_mode),
                    }
                )
                await db.flush()
                if not test_mode:
                    await _maybe_deadletter_after_failure(db, scanner)
                await db.refresh(run)
                return run

        # Final alignment flag for candidates that never hit DIRECTION_ALIGNMENT.
        for cand in candidates:
            if "aligned" not in cand or not align_present:
                cand["aligned"] = _is_aligned(cand)

        aligned = [c for c in candidates if c.get("aligned")]
        top_pick = aligned[0] if aligned else None
        run.result = _attach_repairs(
            {
                "candidates": candidates,
                "top_pick": top_pick,
                "counts": _counts(candidates_n=len(candidates), aligned_n=len(aligned)),
                **_test_mode_result_fields(scanner, test_mode),
            }
        )
        run.status = "empty" if not candidates else "completed"
        run.finished_at = datetime.now(UTC)
        await db.flush()

        # C6: surface fired runs on the signals/toast feed (cooldown-gated).
        # Test-mode runs must stay silent: no alert feed rows and no email
        # (the fired-email hook only runs inside record_scanner_fired_alert).
        if not test_mode:
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
        if not test_mode:
            await _maybe_deadletter_after_failure(db, scanner)
        await db.refresh(run)
        return run
