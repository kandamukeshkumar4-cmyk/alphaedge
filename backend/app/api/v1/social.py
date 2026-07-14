"""Public paper-trader profiles for the social layer."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.social_profiles import get_public_trader_profile

router = APIRouter(prefix="/api/v1/social", tags=["social"])


class PublicTraderProfileResponse(BaseModel):
    username: str
    member_since: datetime
    trade_count: int
    settled_trade_count: int
    win_rate: float
    roi: float
    paper_trading_only: bool = True


@router.get(
    "/traders/{trader}",
    response_model=PublicTraderProfileResponse,
    summary="Get a public trader profile",
    description="Return anonymized public stats for a paper trader without email or user ID fields.",
)
async def get_trader_profile(
    trader: str = Path(min_length=1, max_length=64, description="Anonymized label or display name"),
    db: AsyncSession = Depends(get_db),
) -> PublicTraderProfileResponse:
    profile = await get_public_trader_profile(db, trader)
    if profile is None:
        raise HTTPException(status_code=404, detail="Trader profile not found")
    return PublicTraderProfileResponse(
        username=profile.username,
        member_since=profile.member_since,
        trade_count=profile.trade_count,
        settled_trade_count=profile.settled_trade_count,
        win_rate=profile.win_rate,
        roi=profile.roi,
    )
