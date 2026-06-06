from pathlib import Path
from datetime import UTC, datetime

from arq import cron

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
    ]
    cron_jobs = [
        cron(capture_market_snapshots_task, minute={0}),
        cron(ingest_odds_task, hour={12}, minute=0),
    ]
