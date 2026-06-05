from arq.connections import RedisSettings

from app.core.config import get_settings

settings = get_settings()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 3
    functions = [
        "app.workers.tasks.capture_market_snapshots_task",
        "app.workers.tasks.capture_historical_closing_snapshots_task",
        "app.workers.tasks.ingest_odds_task",
        "app.workers.tasks.run_eval_on_resolve_task",
        "app.workers.tasks.run_backtest_task",
    ]
    on_job_failure = "app.workers.tasks.record_failed_job"
