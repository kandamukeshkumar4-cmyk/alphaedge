import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import DetailedHealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = logging.getLogger(__name__)
settings = get_settings()


async def _table_status(db: AsyncSession, table_name: str) -> str:
    try:
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else "postgresql"

        if dialect_name == "sqlite":
            result = await db.execute(
                text(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = :table_name LIMIT 1"
                ),
                {"table_name": table_name},
            )
        else:
            result = await db.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = :table_name LIMIT 1"
                ),
                {"table_name": table_name},
            )
        return "ok" if result.scalar() is not None else "missing"
    except SQLAlchemyError as exc:
        logger.warning("Table check failed for %s: %s", table_name, exc)
        return "missing"


def _aggregate_status(checks: dict[str, str]) -> str:
    if checks.get("db") == "error":
        return "down"
    if (
        checks.get("paper_orders_table") == "missing"
        or checks.get("users_table") == "missing"
        or checks.get("env_guard") == "FAIL"
    ):
        return "degraded"
    return "ok"


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def get_detailed_health(
    db: AsyncSession = Depends(get_db),
) -> DetailedHealthResponse:
    checks: dict[str, str] = {
        "db": "error",
        "paper_orders_table": "missing",
        "users_table": "missing",
        "env_guard": "FAIL",
    }

    try:
        try:
            await db.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except SQLAlchemyError as exc:
            logger.warning("Database health check failed: %s", exc)
            checks["db"] = "error"

        if checks["db"] == "ok":
            checks["paper_orders_table"] = await _table_status(db, "paper_orders")
            checks["users_table"] = await _table_status(db, "users")

        checks["env_guard"] = "ok" if settings.paper_trading_only else "FAIL"
    except Exception as exc:
        logger.exception("Detailed health check encountered an unexpected error: %s", exc)

    return DetailedHealthResponse(
        status=_aggregate_status(checks),
        paper_trading_only=True,
        checks=checks,
        version="0.1.0",
    )
