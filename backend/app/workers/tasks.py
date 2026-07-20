import logging
from pathlib import Path
from datetime import UTC, datetime

from arq import cron
from arq.connections import RedisSettings

from app.agents.graph import prefetch_news_for_market
from app.backtesting.replay import run_backtest, run_phase3_snapshot_matrix_backtest
from app.core.config import get_settings
from app.data_quality.checks import run_quality_checks
from app.db.models import JobRun
from app.eval.service import EvalService
from app.pipeline.ingest import MarketSnapshotCaptureResult
from app.pipeline.ingest import (
    capture_configured_historical_closing_snapshots,
    capture_configured_market_snapshots,
    ingest_fixtures,
)
from app.workers.ops_alerts import ops_alerts_task
from app.workers.order_expiry import order_expiry_task
from app.workers.portfolio_equity import portfolio_equity_snapshot_task
from app.workers.drift_detect import drift_detect_task
from app.workers.model_retrain import model_retrain_task
from app.workers.external_market_bridge import external_market_bridge_task
from app.workers.catalog_market_resolver import catalog_market_resolve_task
from app.workers.forecast_autolock import forecast_autolock_task
from app.workers.daily_digest import daily_digest_task
from app.workers.jobrun_retention import jobrun_retention_task
from app.workers.data_retention import data_retention_task


logger = logging.getLogger(__name__)

CAPTURE_MARKET_SNAPSHOTS_JOB_NAME = "capture_market_snapshots_task"
CAPTURE_HISTORICAL_CLOSING_SNAPSHOTS_JOB_NAME = (
    "capture_historical_closing_snapshots_task"
)


async def capture_market_snapshots_task(ctx: dict) -> dict:
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    connectors = ctx.get("market_data_connectors")
    started_at = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        result = await capture_configured_market_snapshots(
            session,
            settings=settings,
            connectors=connectors,
        )
        summary = _market_snapshot_capture_summary(result)
        session.add(
            JobRun(
                job_name=CAPTURE_MARKET_SNAPSHOTS_JOB_NAME,
                status="degraded" if result.failed else "success",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                summary=summary,
            )
        )
        await session.commit()
    return summary


async def capture_historical_closing_snapshots_task(ctx: dict) -> dict:
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    connectors = ctx.get("market_data_connectors")
    started_at = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        result = await capture_configured_historical_closing_snapshots(
            session,
            settings=settings,
            connectors=connectors,
        )
        summary = _market_snapshot_capture_summary(result)
        session.add(
            JobRun(
                job_name=CAPTURE_HISTORICAL_CLOSING_SNAPSHOTS_JOB_NAME,
                status="degraded" if result.failed else "success",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                summary=summary,
            )
        )
        await session.commit()
    return summary


def _market_snapshot_capture_summary(result: MarketSnapshotCaptureResult) -> dict:
    summary = {
        "fetched": result.fetched,
        "ingested": result.inserted,
        "skipped": result.skipped,
        "failed": result.failed,
        "failures": [
            {
                "source": failure.source,
                "target": failure.target,
                "error": failure.error,
            }
            for failure in result.failures
        ],
    }
    if result.captured_at is not None:
        summary["captured_at"] = result.captured_at.isoformat()
    return summary


async def ingest_odds_task(ctx: dict) -> dict:
    from app.db.session import AsyncSessionLocal

    fixtures = Path(__file__).resolve().parents[3] / "fixtures"
    report = run_quality_checks(
        fixtures / "nba_games_sample.csv",
        fixtures / "odds_snapshots_sample.csv",
        fixtures / "final_scores_sample.csv",
    )
    async with AsyncSessionLocal() as session:
        count = await ingest_fixtures(session, fixtures)
        await session.commit()
    return {"ingested": count, "quality_passed": report.passed, "issues": report.issues}


WC2026_RESOLVE_JOB_NAME = "wc2026_resolve_task"


async def wc2026_resolve_task(ctx: dict) -> dict:
    """Fetch finished WC2026 matches and resolve corresponding markets."""
    from app.db.session import AsyncSessionLocal
    from app.services.wc2026_resolver import resolve_finished_wc2026_markets

    started_at = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        summary = await resolve_finished_wc2026_markets(session)
        session.add(
            JobRun(
                job_name=WC2026_RESOLVE_JOB_NAME,
                status="success",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                summary=summary,
            )
        )
        await session.commit()
    return summary


RESOLVE_EXTERNAL_MARKETS_JOB_NAME = "resolve_external_markets_task"


async def resolve_external_markets_task(ctx: dict) -> dict:
    """V14 F02/F03: resolve past-close external markets from real venue data and
    score their locked forecasts. Mirrors wc2026_resolve_task (JobRun heartbeat +
    config flag). Flag-gated (SCHEDULER_EXTERNAL_RESOLVE_ENABLED, default on)."""
    from app.db.session import AsyncSessionLocal
    from app.services.external_market_resolver import resolve_external_markets

    settings = ctx.get("settings") or get_settings()
    if not settings.scheduler_external_resolve_enabled:
        return {"skipped": True, "reason": "SCHEDULER_EXTERNAL_RESOLVE_ENABLED=false"}

    started_at = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        summary = await resolve_external_markets(
            session, limit=settings.external_resolve_batch
        )
        session.add(
            JobRun(
                job_name=RESOLVE_EXTERNAL_MARKETS_JOB_NAME,
                status="degraded" if summary.get("errors") else "success",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                summary=summary,
            )
        )
        await session.commit()
    return summary


FETCH_NEWS_SIGNALS_JOB_NAME = "fetch_news_signals_task"


async def fetch_news_signals_task(ctx: dict) -> dict:
    """Pre-warm the news signal cache for all tracked market slugs.

    Runs hourly. Skips gracefully if NEWS_SIGNALS_ENABLED=false or no slugs.
    """
    settings = ctx.get("settings") or get_settings()
    if not settings.news_signals_enabled:
        return {"skipped": True, "reason": "NEWS_SIGNALS_ENABLED=false"}

    slugs = settings.polymarket_market_slug_list
    if not slugs:
        return {"fetched": 0, "slugs": []}

    timeout = settings.news_signals_timeout
    results: dict[str, str] = {}
    for slug in slugs:
        try:
            await prefetch_news_for_market(slug, timeout=timeout)
            results[slug] = "ok"
        except Exception as exc:
            results[slug] = f"error: {exc}"

    return {"fetched": sum(1 for v in results.values() if v == "ok"), "slugs": results}


NEWS_SCAN_JOB_NAME = "news_scan_task"
_NEWS_SCAN_TOP_N = 10  # Exa-quota guard: only the most active markets per pass


async def news_scan_task(ctx: dict) -> dict:
    """Hourly (B04): fetch real news per top market and feed the news-lag
    detector so news_arrival SignalEvents exist for the analyst to cite.

    Before this task, NewsLagService.detect had NO production caller -- the
    news evidence layer was structurally empty no matter which API keys were
    configured. Skips markets without a news signal; never raises per-market.
    """
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    if not settings.news_signals_enabled:
        return {"skipped": True, "reason": "NEWS_SIGNALS_ENABLED=false"}

    async with AsyncSessionLocal() as session:
        results = await run_news_scan(session, settings=settings)
        await session.commit()
    return {"scanned": len(results), "results": results}


async def run_news_scan(session, *, settings=None, now=None) -> dict[str, str]:
    """Core of news_scan_task on a caller-provided session (testable without
    the app engine)."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from datetime import timedelta

    from sqlalchemy import select as _select

    from app.core.config import get_settings as _get_settings
    from app.db.models import Market as _Market
    from app.db.models import MarketSentimentSnapshot as _MarketSentimentSnapshot
    from app.db.models import MarketStatus as _MarketStatus
    from app.db.models import OddsSnapshot as _OddsSnapshot
    from app.signals.news_lag import NewsLagService
    from app.signals.news_cadence import (
        HOT_INTERVAL_SEC,
        NewsRefreshCandidate,
        eligible_candidates,
        fallback_eligible_candidates,
        record_refresh_failure,
        record_refresh_success,
        refresh_interval_sec,
    )
    from app.signals.news_signal import fetch_news_signal
    from app.signals.sentiment_debate import persist_debate, run_news_debate
    from app.services.whale_flow_service import WhaleFlowService

    settings = settings or _get_settings()
    now = now or _dt.now(_UTC)
    results: dict[str, str] = {}
    rows = (
        await session.execute(
            _select(_Market.slug, _Market.title, _Market.lock_at, _Market.volume)
            .where(
                _Market.status == _MarketStatus.OPEN,
                _Market.source.in_(("polymarket", "kalshi")),
            )
            .order_by(_Market.volume.desc())
            .limit(max(_NEWS_SCAN_TOP_N, int(settings.news_cadence_budget)))
        )
    ).all()
    candidates: list[NewsRefreshCandidate] = []
    titles: dict[str, str] = {}
    whale_service = WhaleFlowService(session)
    for slug, title, lock_at, volume in rows:
        # latest-minus-oldest over the 1h window (not the two oldest rows).
        window = (
            _OddsSnapshot.market_slug == slug,
            _OddsSnapshot.captured_at >= now - timedelta(hours=1),
            _OddsSnapshot.captured_at <= now,
        )
        oldest = (
            await session.execute(
                _select(_OddsSnapshot.implied_yes, _OddsSnapshot.captured_at)
                .where(*window)
                .order_by(_OddsSnapshot.captured_at.asc())
                .limit(1)
            )
        ).first()
        newest = (
            await session.execute(
                _select(_OddsSnapshot.implied_yes, _OddsSnapshot.captured_at)
                .where(*window)
                .order_by(_OddsSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()
        if (
            oldest is not None
            and newest is not None
            and oldest[1] != newest[1]
        ):
            delta = float(newest[0] - oldest[0])
        else:
            delta = None
        pressure = await whale_service.pressure_for(slug)
        candidates.append(NewsRefreshCandidate(
            slug=slug,
            close_at=lock_at,
            price_delta_1h=delta,
            whale_pressure=pressure.pressure,
            volume=int(volume or 0),
        ))
        titles[slug] = title
    if not settings.news_cadence_enabled:
        # Restore pre-V61 hourly-equivalent volume: 5-min loop + no cooldown
        # would 12x external news calls. Per-slug 60min cooldown keeps cadence.
        selected = fallback_eligible_candidates(
            candidates,
            budget=_NEWS_SCAN_TOP_N,
        )
    else:
        selected = eligible_candidates(
            candidates,
            now=now,
            budget=max(0, int(settings.news_cadence_budget)),
            price_jump_threshold=float(settings.news_cadence_price_jump),
            whale_spike_threshold=float(settings.news_cadence_whale_spike),
        )
    service = NewsLagService(session)
    for candidate in selected:
        slug = candidate.slug
        try:
            signal = await fetch_news_signal(titles[slug])
            if signal is None:
                results[slug] = "no-news"
                record_refresh_success(slug)
                continue
            session.add(_MarketSentimentSnapshot(
                market_slug=slug,
                sentiment_score=max(-1.0, min(1.0, float(signal.sentiment_score))),
                volume_score=max(0.0, min(1.0, float(signal.volume_score))),
                sources_count=max(0, int(signal.sources_count)),
                source="public-news",
                captured_at=now,
            ))
            if signal.sentiment_score == 0.0:
                results[slug] = "neutral-news"
                record_refresh_success(slug)
                continue
            if refresh_interval_sec(
                candidate,
                now=now,
                price_jump_threshold=float(settings.news_cadence_price_jump),
                whale_spike_threshold=float(settings.news_cadence_whale_spike),
            ) == HOT_INTERVAL_SEC:
                verdicts = await run_news_debate(
                    candidate=candidate,
                    title=titles[slug],
                    headline=signal.headline,
                    sentiment_score=signal.sentiment_score,
                    settings=settings,
                    now=now,
                )
                if len(verdicts) == 3:
                    persist_debate(session, market_slug=slug, verdicts=verdicts)
            outcome = await service.detect(
                slug,
                relevance=max(0.0, min(1.0, signal.volume_score)),
                sentiment=signal.sentiment_score,
                news_ts=_dt.now(_UTC),
                headline=signal.headline,
            )
            results[slug] = outcome.reason
            record_refresh_success(slug)
        except Exception as exc:  # noqa: BLE001 - per-market isolation
            results[slug] = f"error: {exc}"
            record_refresh_failure()
    return results


NEWS_MISPRICING_JOB_NAME = "news_mispricing_scan_task"


async def news_mispricing_scan_task(ctx: dict) -> dict:
    """G03: emit ``news:mispricing`` when model_p diverges from market_p after
    fresh news. Analysis only — no order path.
    """
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = get_settings()
    if not settings.news_mispricing_enabled:
        return {"scanned": 0, "emitted": 0, "skipped": "disabled"}

    async with AsyncSessionLocal() as session:
        emitted = await run_news_mispricing_scan(session)
        await session.commit()
    return {"scanned": emitted.get("scanned", 0), "emitted": emitted.get("emitted", 0)}


async def run_news_mispricing_scan(session) -> dict:
    """Core of news_mispricing_scan_task (testable; inject news via monkeypatch)."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from sqlalchemy import select as _select

    from app.core.config import get_settings
    from app.db.models import Market as _Market
    from app.db.models import MarketStatus as _MarketStatus
    from app.db.models import OddsSnapshot, SignalEvent
    from app.services.forecast_service import ForecastService
    from app.signals.news_mispricing import (
        NewsMispricingInput,
        news_mispricing_to_events,
    )
    from app.signals.news_signal import fetch_news_signal

    settings = get_settings()
    now = _dt.now(_UTC)
    rows = (
        await session.execute(
            _select(_Market.slug, _Market.title, _Market.source)
            .where(
                _Market.status == _MarketStatus.OPEN,
                _Market.source.in_(("polymarket", "kalshi")),
            )
            .order_by(_Market.volume.desc())
            .limit(_NEWS_SCAN_TOP_N)
        )
    ).all()

    candidates: list[NewsMispricingInput] = []
    for slug, title, source in rows:
        try:
            signal = await fetch_news_signal(title)
            if signal is None:
                continue
            market_p = await session.scalar(
                _select(OddsSnapshot.implied_yes)
                .where(OddsSnapshot.market_slug == slug)
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(1)
            )
            if market_p is None:
                continue
            market_p_f = float(market_p)
            forecast = ForecastService.predict(slug, implied_yes=market_p_f)
            if forecast is None:
                continue
            news_ts = signal.published_at or now
            candidates.append(
                NewsMispricingInput(
                    market_slug=slug,
                    platform=str(source or "polymarket"),
                    model_p=forecast.model_prob,
                    market_p=market_p_f,
                    news_id=signal.news_id,
                    news_url=signal.news_url,
                    news_ts=news_ts,
                    headline=signal.headline,
                )
            )
        except Exception as exc:  # noqa: BLE001 - per-market isolation
            logger.warning("news mispricing scan failed for %s: %s", slug, exc)

    events = news_mispricing_to_events(
        candidates,
        now=now,
        threshold=settings.news_mispricing_threshold,
        window_sec=settings.news_mispricing_window_sec,
    )
    for event in events:
        session.add(SignalEvent(**event))
    await session.flush()
    return {"scanned": len(rows), "emitted": len(events)}


UNUSUAL_FLOW_JOB_NAME = "unusual_flow_scan_task"


async def unusual_flow_scan_task(ctx: dict) -> dict:
    """G04: emit ``anomaly:unusual_flow`` when a price jump / volume spike has
    NO matching news item in the window. Analysis only — no order path.
    """
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = get_settings()
    if not settings.unusual_flow_enabled:
        return {"scanned": 0, "emitted": 0, "skipped": "disabled"}

    async with AsyncSessionLocal() as session:
        result = await run_unusual_flow_scan(session)
        await session.commit()
    return {"scanned": result.get("scanned", 0), "emitted": result.get("emitted", 0)}


async def run_unusual_flow_scan(session) -> dict:
    """Core of unusual_flow_scan_task (testable; inject news via monkeypatch).

    Candidates come from the diff engine's persisted ``delta:price_jump`` /
    ``delta:volume_surge`` SignalEvents (single source of truth for "the market
    moved"); the news-window check is shared with G03 via
    ``news_in_window`` inside ``evaluate_unusual_flow``.
    """
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from sqlalchemy import select as _select

    from app.core.config import get_settings
    from app.db.models import Market as _Market
    from app.db.models import SignalEvent
    from app.signals.news_signal import fetch_news_signal
    from app.signals.unusual_flow import (
        ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
        UnusualFlowInput,
        unusual_flow_to_events,
    )

    settings = get_settings()
    now = _dt.now(_UTC)
    cutoff = now - _td(seconds=settings.unusual_flow_lookback_sec)

    delta_rows = (
        (
            await session.execute(
                _select(SignalEvent)
                .where(
                    SignalEvent.signal_type.in_(
                        ("delta:price_jump", "delta:volume_surge")
                    ),
                    SignalEvent.created_at >= cutoff,
                )
                .order_by(SignalEvent.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    # Per-market anomaly dedupe: one anomaly per market per lookback horizon.
    already_flagged = set(
        (
            await session.execute(
                _select(SignalEvent.market_id).where(
                    SignalEvent.signal_type == ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
                    SignalEvent.created_at >= cutoff,
                )
            )
        ).scalars()
    )

    # Newest delta per market wins (rows are newest-first).
    latest_by_market: dict[str, SignalEvent] = {}
    for row in delta_rows:
        if row.market_id in already_flagged:
            continue
        latest_by_market.setdefault(row.market_id, row)

    candidates: list[UnusualFlowInput] = []
    for slug, delta in latest_by_market.items():
        try:
            title = await session.scalar(
                _select(_Market.title).where(_Market.slug == slug)
            )
            if not title:
                continue  # unjoinable slug — no title to search news for
            payload = delta.payload if isinstance(delta.payload, dict) else {}
            occurred_ts = _parse_occurred_ts(payload.get("occurred_ts")) or (
                delta.created_at
                if delta.created_at.tzinfo is not None
                else delta.created_at.replace(tzinfo=_UTC)
            )
            signal = await fetch_news_signal(title)
            if signal is not None and signal.published_at is None:
                # News exists but carries no timestamp: conservatively assume
                # it is a fresh catalyst — never flag an anomaly on ambiguity.
                continue
            candidates.append(
                UnusualFlowInput(
                    market_slug=slug,
                    platform=delta.platform or "stream",
                    kind=str(payload.get("kind") or delta.signal_type.split(":")[-1]),
                    direction=str(payload.get("direction") or ""),
                    magnitude=float(payload.get("magnitude") or 0.0),
                    occurred_ts=occurred_ts,
                    news_ts=signal.published_at if signal is not None else None,
                    headline=signal.headline if signal is not None else "",
                    detail=(
                        payload.get("detail")
                        if isinstance(payload.get("detail"), dict)
                        else {}
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - per-market isolation
            logger.warning("unusual flow scan failed for %s: %s", slug, exc)

    events = unusual_flow_to_events(
        candidates, window_sec=settings.unusual_flow_window_sec
    )
    for event in events:
        session.add(SignalEvent(**event))
    await session.flush()
    return {"scanned": len(latest_by_market), "emitted": len(events)}


def _parse_occurred_ts(value: object):
    """Parse an ISO occurred_ts from a delta payload; None when absent/invalid."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = _dt.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=_UTC)


WEATHER_SCAN_JOB_NAME = "weather_scan_task"


async def weather_scan_task(ctx: dict) -> dict:
    """O04: price NWS forecasts vs Kalshi daily-high books and persist the
    strongest per-city edges as delta:weather_edge SignalEvents so they surface
    in /signals, the ticker, and the engine room. Signals only — no order path.
    """
    import asyncio
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from app.db.session import AsyncSessionLocal
    from app.services.weather_desk import WeatherDeskService

    # Tomorrow: today's daily-high books close overnight.
    day = (_dt.now(_UTC) + _td(days=1)).date()
    try:
        cities = await asyncio.to_thread(WeatherDeskService().scan, day)
    except Exception as exc:  # noqa: BLE001 - never crash the scheduler
        logger.warning("Weather scan failed: %s", exc)
        return {"scanned": 0, "emitted": 0, "error": str(exc)}

    async with AsyncSessionLocal() as session:
        emitted = await run_weather_scan(session, cities)
        logged = await log_weather_forecasts(session, cities, day)
        await session.commit()
    return {"scanned": len(cities), "emitted": emitted, "forecasts_logged": logged}


async def run_weather_scan(session, cities: list[dict]) -> int:
    """Core of weather_scan_task on a caller-provided session + pre-scanned
    cities (testable without network). Persists one delta:weather_edge
    SignalEvent per city edge; returns the count emitted.

    V34: market_ids are canonical ``ks-…`` slugs. After emit, rekey any recent
    raw-ticker orphans left by older code (idempotent).
    """
    from app.data_quality.hygiene import rekey_orphan_signal_market_ids
    from app.db.models import SignalEvent
    from app.services.weather_desk import weather_scan_to_events

    events = weather_scan_to_events(cities)
    for event in events:
        session.add(SignalEvent(**event))
    await session.flush()
    await rekey_orphan_signal_market_ids(session, limit=200)
    return len(events)


async def log_weather_forecasts(session, cities: list[dict], day) -> int:
    """O05: upsert one WeatherForecastLog row per city for ``day`` (the forecast
    high + sigma the model used). One row per (city, target_date) — re-scanning
    the same day updates the forecast, it does not duplicate. Actuals are filled
    later by record_weather_actuals. Testable with a caller-provided session."""
    from decimal import Decimal

    from sqlalchemy import select as _select

    from app.db.models import WeatherForecastLog

    logged = 0
    for report in cities:
        city = report.get("city")
        forecast = report.get("forecast_high_f")
        if city is None or forecast is None:
            continue
        sigma = report.get("sigma_f")
        existing = await session.scalar(
            _select(WeatherForecastLog).where(
                WeatherForecastLog.city == city,
                WeatherForecastLog.target_date == day,
            )
        )
        if existing is not None:
            existing.forecast_high_f = Decimal(str(forecast))
            if sigma is not None:
                existing.sigma_used = Decimal(str(sigma))
        else:
            session.add(
                WeatherForecastLog(
                    city=city,
                    target_date=day,
                    forecast_high_f=Decimal(str(forecast)),
                    sigma_used=Decimal(str(sigma if sigma is not None else 0)),
                    source=str(report.get("source") or "nws.point-forecast"),
                )
            )
        logged += 1
    await session.flush()
    return logged


async def record_weather_actuals(session, actuals: dict, *, now=None) -> int:
    """O05: fill actual_high_f (+ resolved_at) for unresolved forecast rows.
    ``actuals`` maps (city, target_date) -> observed high F. Idempotent: only
    rows with a NULL actual are touched. Returns the number resolved."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from decimal import Decimal

    from sqlalchemy import select as _select

    from app.db.models import WeatherForecastLog

    now = now or _dt.now(_UTC)
    resolved = 0
    for (city, target_date), actual in actuals.items():
        if actual is None:
            continue
        row = await session.scalar(
            _select(WeatherForecastLog).where(
                WeatherForecastLog.city == city,
                WeatherForecastLog.target_date == target_date,
                WeatherForecastLog.actual_high_f.is_(None),
            )
        )
        if row is None:
            continue
        row.actual_high_f = Decimal(str(actual))
        row.resolved_at = now
        resolved += 1
    await session.flush()
    return resolved


async def run_eval_on_resolve_task(ctx: dict, market_id: str) -> dict:
    from uuid import UUID

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        svc = EvalService(session)
        result = await svc.evaluate_market(UUID(market_id))
        await session.commit()
        return {"evaluation_id": str(result.id), "brier": float(result.brier_score)}


async def run_backtest_task(ctx: dict) -> dict:
    fixtures = Path(__file__).resolve().parents[3] / "fixtures"
    artifact_dir = _artifact_dir_from_ctx(ctx)
    source = ctx.get("source", "fixtures")
    if source == "snapshot_store":
        from app.db.session import AsyncSessionLocal
        from app.ml.snapshot_dataset import load_resolved_snapshot_feature_matrix

        async with AsyncSessionLocal() as session:
            matrix = await load_resolved_snapshot_feature_matrix(session)
        return run_phase3_snapshot_matrix_backtest(matrix, artifact_dir)
    if source != "fixtures":
        raise ValueError("run_backtest_task source must be fixtures or snapshot_store")
    return run_backtest(fixtures, artifact_dir)


def _artifact_dir_from_ctx(ctx: dict) -> Path | None:
    raw = ctx.get("artifact_dir")
    if raw is None:
        return None
    return Path(raw)


REFRESH_WHALES_JOB_NAME = "refresh_whales_task"
SNAPSHOT_WHALES_JOB_NAME = "snapshot_whale_positions_task"
WHALE_FLOW_JOB_NAME = "whale_flow_task"


async def whale_flow_task(ctx: dict) -> dict:
    """Loop V58 D1: poll Polymarket data-api large trades → whale_events.

    Bounded, rate-limited, circuit-broken. Analysis only — no order path.
    """
    from app.db.session import AsyncSessionLocal
    from app.services.whale_flow_service import WhaleFlowService

    settings = get_settings()
    if not settings.whale_flow_enabled:
        return {"skipped": True, "reason": "WHALE_FLOW_ENABLED=false"}

    async with AsyncSessionLocal() as session:
        service = WhaleFlowService(session)
        summary = await service.poll_and_store(force=bool(ctx.get("force")))
        await session.commit()
    return summary


VENUE_GAP_JOB_NAME = "venue_gap_task"


async def venue_gap_task(ctx: dict) -> dict:
    """Loop V58 D2: recompute PM↔Kalshi implied gaps from odds snapshots."""
    from app.db.session import AsyncSessionLocal
    from app.services.venue_gap_service import VenueGapService

    settings = get_settings()
    if not settings.venue_gap_enabled:
        return {"skipped": True, "reason": "VENUE_GAP_ENABLED=false"}

    async with AsyncSessionLocal() as session:
        service = VenueGapService(session)
        summary = await service.refresh_gaps()
        await session.commit()
    return summary


async def refresh_whales_task(ctx: dict) -> dict:
    """Weekly: pull the Polymarket data-api leaderboard, qualify each wallet from its
    trade history, and upsert TrackedWallet rows. Read-only; no execution."""
    import asyncio

    from app.data.connectors.polymarket_data_api import PolymarketDataApiConnector
    from app.db.session import AsyncSessionLocal
    from app.services.whale_tracker_service import WhaleTrackerService

    connector = PolymarketDataApiConnector()
    started_at = datetime.now(UTC)
    qualified = evaluated = 0
    try:
        entries = await asyncio.to_thread(connector.fetch_leaderboard, limit=200)
    except Exception as error:  # noqa: BLE001 - external API, degrade gracefully
        logger.warning("Whale leaderboard fetch failed: %s", error)
        return {"skipped": True, "reason": "leaderboard_fetch_failed"}

    async with AsyncSessionLocal() as session:
        service = WhaleTrackerService(session)
        for entry in entries:
            try:
                trades = await asyncio.to_thread(
                    connector.fetch_closed_positions, entry.wallet_address
                )
            except Exception as error:  # noqa: BLE001 - per-wallet isolation
                logger.warning("Trades fetch failed for %s: %s", entry.wallet_address, error)
                continue
            stats = _wallet_stats_from_trades(trades)
            evaluated += 1
            result = await service.upsert_qualification(entry.wallet_address, stats)
            if result.qualified:
                qualified += 1
        await session.commit()
    return {
        "evaluated": evaluated,
        "qualified": qualified,
        "started_at": started_at.isoformat(),
    }


def _wallet_stats_from_trades(trades):
    """Derive WalletStats from resolved trades (wins/losses/top win)."""
    from decimal import Decimal

    from app.signals.smart_money import WalletStats

    resolved = [t for t in trades if t.resolved]
    wins = [t for t in resolved if t.pnl > 0]
    losses = [t for t in resolved if t.pnl < 0]
    gross_profit = sum((t.pnl for t in wins), Decimal("0"))
    gross_loss = sum((-t.pnl for t in losses), Decimal("0"))
    top_win = max((t.pnl for t in wins), default=Decimal("0"))
    return WalletStats(
        resolved_count=len(resolved),
        wins=len(wins),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        top_win=top_win,
    )


async def snapshot_whale_positions_task(ctx: dict) -> dict:
    """Every ~3 min: snapshot qualified wallets' positions and diff into whale_delta
    events that feed the alignment scorer. Read-only; no execution."""
    import asyncio

    from sqlalchemy import select

    from app.data.connectors.polymarket_data_api import PolymarketDataApiConnector
    from app.db.models import TrackedWallet
    from app.db.session import AsyncSessionLocal
    from app.services.whale_tracker_service import WhaleTrackerService

    connector = PolymarketDataApiConnector()
    deltas = wallets = 0
    async with AsyncSessionLocal() as session:
        addresses = (
            await session.execute(
                select(TrackedWallet.wallet_address).where(TrackedWallet.qualified.is_(True))
            )
        ).scalars().all()
        service = WhaleTrackerService(session)
        for address in addresses:
            try:
                positions = await asyncio.to_thread(connector.fetch_positions, address)
            except Exception as error:  # noqa: BLE001 - per-wallet isolation
                logger.warning("Positions fetch failed for %s: %s", address, error)
                continue
            events = await service.snapshot_and_diff(address, positions)
            wallets += 1
            deltas += len(events)
        await session.commit()
    return {"wallets": wallets, "deltas": deltas}


SCORE_CLAIMS_JOB_NAME = "score_claims_task"
ANALYST_AGGREGATES_JOB_NAME = "analyst_aggregates_task"


async def score_claims_task(ctx: dict) -> dict:
    """Every 15 min: grade analyst claims whose horizon has elapsed. Read-only."""
    from app.db.session import AsyncSessionLocal
    from app.eval.claim_scorer import ClaimScorerService

    settings = ctx.get("settings") or get_settings()
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        service = ClaimScorerService(session, epsilon=settings.eval_claim_epsilon)
        counts = await service.score_pending(now=now)
        await session.commit()
    return counts


async def analyst_aggregates_task(ctx: dict) -> dict:
    """Hourly: recompute the public track-record aggregates."""
    from app.db.session import AsyncSessionLocal
    from app.eval.analyst_metrics import AnalystMetricsService

    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        n = await AnalystMetricsService(session).recompute(now=now)
        await session.commit()
    return {"aggregates": n}


MORNING_RESEARCH_JOB_NAME = "morning_research_task"


async def morning_research_task(ctx: dict) -> dict:
    """Daily: sweep top-moving markets, run the analyst on each, write a digest,
    and optionally distribute it to notification channels (T14, off by default)."""
    from app.db.session import AsyncSessionLocal
    from app.services.digest_distribution import DigestDistributionService
    from app.services.research_digest_service import ResearchDigestService

    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        summary = await ResearchDigestService(session).run_daily(now=now)
        distribution: dict = {"dispatched": False}
        try:
            distribution = await DigestDistributionService(session).distribute(summary, now=now)
            await _attach_distribution_metadata(session, now, distribution)
        except Exception:  # noqa: BLE001 - distribution must not fail the digest
            logger.warning("Digest distribution failed", exc_info=True)
        await session.commit()
    return {**summary, "distribution": distribution}


async def _attach_distribution_metadata(session, now, distribution: dict) -> None:
    """Record channels attempted/sent on today's digest row (spec: digest row gains
    distribution metadata)."""
    from sqlalchemy import select

    from app.db.models import AnalystBrief

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    digest = await session.scalar(
        select(AnalystBrief)
        .where(AnalystBrief.kind == "digest", AnalystBrief.created_at >= day_start)
        .order_by(AnalystBrief.created_at.desc())
        .limit(1)
    )
    if digest is not None:
        citations = list(digest.citations or [])
        citations.append({"kind": "model", "ref": "distribution", "url": None, "distribution": distribution})
        digest.citations = citations


NIGHTLY_BACKTEST_JOB_NAME = "nightly_backtest_task"


async def nightly_backtest_task(ctx: dict) -> dict:
    """Nightly: run replay on configured market slugs and publish to backtest_runs.

    Flag-gated: BACKTEST_NIGHTLY_ENABLED must be true.  OFF by default.
    Paper-only — does not route through OrderBookService or RiskService.
    """
    from datetime import timedelta

    from app.backtesting.snapshot_replay import run_snapshot_replay
    from app.db.models import BacktestRun
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    if not settings.backtest_nightly_enabled:
        return {"skipped": True, "reason": "BACKTEST_NIGHTLY_ENABLED=false"}

    slugs = [s.strip() for s in settings.backtest_nightly_slugs.split(",") if s.strip()]
    if not slugs:
        return {"skipped": True, "reason": "no slugs configured"}

    import uuid
    from decimal import Decimal

    now = datetime.now(UTC)
    end_date = now
    start_date = now - timedelta(days=7)
    results: dict[str, str] = {}

    for slug in slugs:
        try:
            async with AsyncSessionLocal() as session:
                result = await run_snapshot_replay(session, slug, start_date, end_date)
                equity_curve_json = [
                    {"timestamp": pt.timestamp.isoformat(), "equity": pt.equity}
                    for pt in result.equity_curve
                ]
                brier_json = [
                    {
                        "timestamp": pt.timestamp.isoformat(),
                        "brier": pt.brier,
                        "sample_count": pt.sample_count,
                    }
                    for pt in result.brier_over_time
                ]
                fill_quality_json = None
                if result.fill_quality is not None:
                    fq = result.fill_quality
                    fill_quality_json = {
                        "trade_count": fq.trade_count,
                        "mean_slippage": fq.mean_slippage,
                        "max_slippage": fq.max_slippage,
                        "total_realized_pnl": fq.total_realized_pnl,
                        "mean_realized_pnl": fq.mean_realized_pnl,
                    }
                run_row = BacktestRun(
                    id=uuid.uuid4(),
                    market_slug=slug,
                    start_date=start_date,
                    end_date=end_date,
                    initial_equity=Decimal("10000"),
                    final_equity=Decimal(str(result.final_equity)),
                    snapshot_count=result.snapshot_count,
                    trade_count=len([t for t in result.trades if t.side in ("yes_buy", "no_buy")]),
                    brier_final=Decimal(str(round(result.brier_final, 6))) if result.brier_final else None,
                    no_lookahead_verified=result.no_lookahead_verified,
                    insufficient_data=result.insufficient_data,
                    equity_curve=equity_curve_json,
                    fill_quality=fill_quality_json,
                    brier_over_time=brier_json,
                    status="completed",
                    paper_trading_only=True,
                )
                session.add(run_row)
                session.add(
                    JobRun(
                        job_name=NIGHTLY_BACKTEST_JOB_NAME,
                        status="success",
                        started_at=now,
                        finished_at=datetime.now(UTC),
                        summary={"slug": slug, "snapshots": result.snapshot_count},
                    )
                )
                await session.commit()
            results[slug] = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Nightly backtest failed for %s: %s", slug, exc)
            results[slug] = f"error: {exc}"

    return {"results": results}


NIGHTLY_PROFILE_REFRESH_JOB_NAME = "nightly_profile_refresh_task"


async def nightly_profile_refresh_task(ctx: dict) -> dict:
    """Nightly: recompute trader profiles for all users who have placed paper trades.

    Flag-gated: TRADER_PROFILE_ENABLED must be true.  ON by default but will
    simply skip when there are no users with paper trades.

    Privacy: reads ONLY paper_orders (in-app paper activity).  No external data.
    Paper-only — does NOT import OrderBookService or RiskService.
    """
    settings = ctx.get("settings") or get_settings()
    if not settings.trader_profile_enabled:
        return {"skipped": True, "reason": "TRADER_PROFILE_ENABLED=false"}

    from app.db.models import PaperOrder, User
    from app.db.session import AsyncSessionLocal
    from app.services.trader_profile_service import TradeRecord, compute_trader_profile
    from sqlalchemy import select

    refreshed = 0
    async with AsyncSessionLocal() as session:
        # Identify users who have at least one paper trade
        user_ids_result = await session.execute(
            select(PaperOrder.user_id).distinct()
        )
        user_ids = [row[0] for row in user_ids_result.fetchall()]

    for user_id in user_ids:
        try:
            async with AsyncSessionLocal() as session:
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                db_user = user_result.scalar_one_or_none()
                if db_user is None:
                    continue
                bankroll = float(db_user.paper_balance)

                orders_result = await session.execute(
                    select(PaperOrder).where(PaperOrder.user_id == user_id)
                )
                db_orders = orders_result.scalars().all()

            trades: list[TradeRecord] = [
                TradeRecord(
                    slug=o.slug,
                    side=o.side,
                    shares=o.shares,
                    price=o.price,
                    cost=o.cost,
                    action=o.action,
                    realized_pnl=o.realized_pnl,
                    settled=o.settled,
                    created_at=o.created_at,
                )
                for o in db_orders
            ]
            # Recompute is a pure function — result not stored separately
            # (profile is always recomputed on-demand from paper_orders).
            # This task warms any future cached-profile layer and validates
            # that the computation does not error for any live user.
            _ = compute_trader_profile(trades, bankroll_usd=bankroll)
            refreshed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Profile refresh failed for user %s: %s", user_id, exc)

    return {"refreshed": refreshed, "total_users": len(user_ids)}


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
    functions = [
        capture_market_snapshots_task,
        capture_historical_closing_snapshots_task,
        ingest_odds_task,
        run_eval_on_resolve_task,
        run_backtest_task,
        fetch_news_signals_task,
        news_scan_task,
        news_mispricing_scan_task,
        unusual_flow_scan_task,
        wc2026_resolve_task,
        resolve_external_markets_task,
        catalog_market_resolve_task,
        refresh_whales_task,
        snapshot_whale_positions_task,
        whale_flow_task,
        venue_gap_task,
        score_claims_task,
        analyst_aggregates_task,
        morning_research_task,
        nightly_backtest_task,
        nightly_profile_refresh_task,
        weather_scan_task,
        order_expiry_task,
        portfolio_equity_snapshot_task,
        ops_alerts_task,
        drift_detect_task,
        model_retrain_task,
        external_market_bridge_task,
        forecast_autolock_task,
        daily_digest_task,
        jobrun_retention_task,
        data_retention_task,
    ]
    cron_jobs = [
        cron(capture_market_snapshots_task, minute={0}),
        cron(ingest_odds_task, hour={12}, minute=0),
        cron(fetch_news_signals_task, minute={30}),  # hourly baseline cache warm
        # V61 S1: 5-minute scheduler; adaptive eligibility keeps non-hot markets hourly.
        cron(news_scan_task, minute=set(range(0, 60, 5))),
        cron(news_mispricing_scan_task, minute={45}),  # G03: news -> news:mispricing
        cron(unusual_flow_scan_task, minute={55}),  # G04: move w/o news -> anomaly
        cron(weather_scan_task, minute={40}),  # O04: NWS-vs-Kalshi weather edges hourly
        cron(wc2026_resolve_task, minute={5, 15, 25, 35, 45, 55}),
        # V14 F02/F03: resolve past-close external markets from venue data + score
        cron(resolve_external_markets_task, minute={10, 40}),
        cron(catalog_market_resolve_task, minute={15, 45}),
        # V33 B2': supply the autolock funnel by registering eligible ingested
        # venue markets. Runs 10 min ahead of autolock so a freshly bridged
        # market is available to the very next lock pass.
        cron(external_market_bridge_task, minute={20, 50}),
        # V16 V4: lock model forecasts pre-close so later venue resolution can grade them
        cron(forecast_autolock_task, minute={0, 30}),
        # weekly whale re-qualification (Mon 03:00); position snapshots every 3 min
        cron(refresh_whales_task, weekday={0}, hour={3}, minute={0}),
        cron(snapshot_whale_positions_task, minute=set(range(0, 60, 3))),
        # Loop V58 D1: large-trade whale flow (~every minute; loop also in-process)
        cron(whale_flow_task, minute=set(range(60))),
        # Loop V58 D2: cross-venue gap refresh every minute
        cron(venue_gap_task, minute=set(range(60))),
        # grade claims every 15 min; recompute the public track record hourly
        cron(score_claims_task, minute={0, 15, 30, 45}),
        cron(analyst_aggregates_task, minute={50}),
        # daily research digest at 06:00 — "the desk runs while you sleep"
        cron(morning_research_task, hour={6}, minute={0}),
        # nightly backtest replay at 02:00 — flag-gated (BACKTEST_NIGHTLY_ENABLED=false)
        cron(nightly_backtest_task, hour={2}, minute={0}),
        # nightly trader profile refresh at 03:30 — flag-gated (TRADER_PROFILE_ENABLED=true)
        cron(nightly_profile_refresh_task, hour={3}, minute={30}),
        cron(order_expiry_task, minute=set(range(60))),
        # B5: daily equity curve snapshots at 00:05 UTC
        cron(portfolio_equity_snapshot_task, hour={0}, minute={5}),
        # E3: ops threshold alerts (error rate / p99 / stale predictions) every 10 min
        cron(ops_alerts_task, minute=set(range(0, 60, 10))),
        # D2: ForecastScore rolling Brier/ECE drift series every 15 min
        cron(drift_detect_task, minute={0, 15, 30, 45}),
        # D4: scheduled XGBoost retrain (flag-gated ML_RETRAIN_ENABLED=false) daily 04:00
        cron(model_retrain_task, hour={4}, minute={0}),
        # Loop V24 N3: daily per-user in-app digest at 07:00 UTC
        cron(daily_digest_task, hour={7}, minute={0}),
        # Loop V37 H3: JobRun retention (flag-gated JOBRUN_RETENTION_ENABLED)
        cron(jobrun_retention_task, hour={5}, minute={15}),
        # Loop V39: data retention (odds downsample / signals / notifications)
        cron(data_retention_task, hour={5}, minute={45}),
    ]
