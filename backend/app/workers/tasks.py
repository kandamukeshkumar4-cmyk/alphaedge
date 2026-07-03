import logging
from pathlib import Path
from datetime import UTC, datetime

from arq import cron

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


async def record_failed_job(ctx: dict, job_name: str, payload: dict, error: str) -> None:
    from app.db.models import FailedJob
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        session.add(
            FailedJob(job_name=job_name, payload=payload, error=error, attempts=3)
        )
        await session.commit()


class WorkerSettings:
    from app.workers.settings import WorkerSettings as _WS

    redis_settings = _WS.redis_settings
    max_tries = 3
    functions = [
        capture_market_snapshots_task,
        capture_historical_closing_snapshots_task,
        ingest_odds_task,
        run_eval_on_resolve_task,
        run_backtest_task,
        fetch_news_signals_task,
        wc2026_resolve_task,
        refresh_whales_task,
        snapshot_whale_positions_task,
        score_claims_task,
        analyst_aggregates_task,
        morning_research_task,
    ]
    cron_jobs = [
        cron(capture_market_snapshots_task, minute={0}),
        cron(ingest_odds_task, hour={12}, minute=0),
        cron(fetch_news_signals_task, minute={30}),  # every hour at :30
        cron(wc2026_resolve_task, minute={5, 15, 25, 35, 45, 55}),
        # weekly whale re-qualification (Mon 03:00); position snapshots every 3 min
        cron(refresh_whales_task, weekday={0}, hour={3}, minute={0}),
        cron(snapshot_whale_positions_task, minute=set(range(0, 60, 3))),
        # grade claims every 15 min; recompute the public track record hourly
        cron(score_claims_task, minute={0, 15, 30, 45}),
        cron(analyst_aggregates_task, minute={50}),
        # daily research digest at 06:00 — "the desk runs while you sleep"
        cron(morning_research_task, hour={6}, minute={0}),
    ]
