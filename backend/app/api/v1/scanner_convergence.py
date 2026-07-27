from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_user
from app.db.models import Scanner, ScannerRun, User
from app.db.session import get_db
from app.services.market_service import MarketService

router = APIRouter(prefix="/api/v1", tags=["scanners"])

class ScannerInfo(BaseModel):
    id: UUID
    name: str
    last_run_at: datetime

class CombinedMarketInfo(BaseModel):
    price: float | None
    volume: int
    lock_at: datetime | None

class ConvergenceItem(BaseModel):
    market_slug: str
    market_title: str
    scanner_count: int
    scanners: list[ScannerInfo]
    combined: CombinedMarketInfo

class ConvergenceResponse(BaseModel):
    items: list[ConvergenceItem]
    scanner_total: int
    computed_at: datetime

@router.get("/scanners/convergence", response_model=ConvergenceResponse)
async def get_scanner_convergence(
    scope: str = Query(..., description="mine|public"),
    min_scanners: int = Query(2, ge=2),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if scope not in ("mine", "public"):
        raise HTTPException(status_code=400, detail="Invalid scope")

    if scope == "mine":
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required for scope=mine")
        clause = Scanner.owner == str(user.id)
    else:
        clause = Scanner.is_public.is_(True)

    scanners = (await db.scalars(select(Scanner).where(clause))).all()

    market_counts: dict[str, int] = {}
    market_scanners: dict[str, list[dict[str, Any]]] = {}

    for scanner in scanners:
        run = await db.scalar(
            select(ScannerRun)
            .where(
                ScannerRun.scanner_id == scanner.id,
                ScannerRun.status == "completed",
            )
            .order_by(ScannerRun.started_at.desc())
            .limit(1)
        )
        if not run:
            continue

        candidates = run.result.get("candidates", []) if isinstance(run.result, dict) else []
        seen_slugs = set()
        for cand in candidates:
            slug = cand.get("market_slug")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            market_counts[slug] = market_counts.get(slug, 0) + 1
            if slug not in market_scanners:
                market_scanners[slug] = []
            market_scanners[slug].append(
                {
                    "id": scanner.id,
                    "name": scanner.name,
                    "last_run_at": run.started_at,
                }
            )

    svc = MarketService(db)
    items = []
    for slug, count in market_counts.items():
        if count < min_scanners:
            continue
        market_res = await svc.get_public_market_by_slug(slug)
        if not market_res:
            continue

        items.append(
            ConvergenceItem(
                market_slug=slug,
                market_title=market_res.title,
                scanner_count=count,
                scanners=market_scanners[slug],
                combined=CombinedMarketInfo(
                    price=market_res.yes_price,
                    volume=market_res.volume,
                    lock_at=market_res.lock_at,
                ),
            )
        )

    items.sort(key=lambda x: (x.scanner_count, x.combined.volume), reverse=True)

    return ConvergenceResponse(
        items=items,
        scanner_total=len(scanners),
        computed_at=datetime.now(UTC),
    )
