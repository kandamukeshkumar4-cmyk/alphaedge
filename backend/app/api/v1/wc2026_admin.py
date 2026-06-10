from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.session import get_db
from app.schemas.wc2026 import WC2026ResolveResponse, WC2026StatusResponse
from app.services.wc2026_resolver import resolve_finished_wc2026_markets, wc2026_admin_status

router = APIRouter(prefix="/api/v1/admin/wc2026", tags=["admin-wc2026"])


@router.post("/resolve", response_model=WC2026ResolveResponse)
async def admin_resolve_wc2026(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> WC2026ResolveResponse:
    summary = await resolve_finished_wc2026_markets(db)
    await db.commit()
    return WC2026ResolveResponse(**summary)


@router.get("/status", response_model=WC2026StatusResponse)
async def admin_wc2026_status(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> WC2026StatusResponse:
    summary = await wc2026_admin_status(db)
    return WC2026StatusResponse(**summary)
