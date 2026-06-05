from pathlib import Path

from arq import cron

from app.backtesting.replay import run_backtest
from app.core.config import get_settings
from app.data_quality.checks import run_quality_checks
from app.eval.service import EvalService
from app.pipeline.ingest import capture_configured_market_snapshots, ingest_fixtures


async def capture_market_snapshots_task(ctx: dict) -> dict:
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    connectors = ctx.get("market_data_connectors")
    async with AsyncSessionLocal() as session:
        result = await capture_configured_market_snapshots(
            session,
            settings=settings,
            connectors=connectors,
        )
        await session.commit()
    return {
        "fetched": result.fetched,
        "ingested": result.inserted,
        "skipped": result.skipped,
    }


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
    return run_backtest(fixtures)


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
        ingest_odds_task,
        run_eval_on_resolve_task,
        run_backtest_task,
    ]
    cron_jobs = [
        cron(capture_market_snapshots_task, minute={0}),
        cron(ingest_odds_task, hour={12}, minute=0),
    ]
