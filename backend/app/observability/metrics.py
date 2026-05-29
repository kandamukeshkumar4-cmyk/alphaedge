from fastapi import APIRouter

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics():
    return {
        "brier_score_rolling_7d": 0.0,
        "fills_total": 0,
        "ingestion_failures": 0,
        "api_latency_p99_ms": 0,
        "token_cost_usd": 0.0,
    }
