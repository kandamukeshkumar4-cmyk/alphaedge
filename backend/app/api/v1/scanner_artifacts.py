"""Scanner run artifact API (loop116) — the rendered fired-alert dashboard.

One read-only endpoint that returns the structured document for a finished
scanner run: headline, fired flag, run meta, KPI tiles, per-step counters, the
matched-markets table, one chart series, and the two narrative sections.

Visibility mirrors ``scanners.py`` exactly: public scanners are readable by
anyone, private ones only by their owner, and a miss is always a 404 (never a
403) so scanner existence does not leak.

Research output only — this router never imports RiskService or
OrderBookService and never creates an order.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_user
from app.db.models import Scanner, ScannerRun, User
from app.db.session import get_db
from app.services.scanner_artifact_service import assemble_run_artifact

router = APIRouter(prefix="/api/v1/scanners", tags=["scanners"])


class ScannerRunArtifactOut(BaseModel):
    """Rendered dashboard document for one scanner run."""

    artifact_version: int
    headline: str
    fired: bool
    run_meta: dict[str, Any]
    kpis: list[dict[str, Any]] = Field(default_factory=list)
    step_counters: list[dict[str, Any]] = Field(default_factory=list)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    chart: dict[str, Any] = Field(default_factory=dict)
    narrative: dict[str, Any] = Field(default_factory=dict)
    generated_at: str
    #: "stored" when the executor persisted it at run completion, "on-read" when
    #: it was assembled deterministically for this request (older/failed runs).
    source: str = "stored"


async def _visible_scanner(
    db: AsyncSession, scanner_id: UUID, user: User | None
) -> Scanner:
    scanner = await db.get(Scanner, scanner_id)
    if scanner is None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    owner_id = str(user.id) if user is not None else None
    if scanner.is_public or (owner_id is not None and scanner.owner == owner_id):
        return scanner
    raise HTTPException(status_code=404, detail="Scanner not found")


@router.get(
    "/{scanner_id}/runs/{run_id}/artifact",
    response_model=ScannerRunArtifactOut,
    summary="Rendered dashboard artifact for one scanner run",
    description=(
        "Returns the run's result document: headline, fired flag, KPI tiles, "
        "per-step counters, matched markets, chart series and the two narrative "
        "sections. Research only — the narrative never contains trade "
        "instructions. Public scanners are readable by anyone; private scanners "
        "only by their owner."
    ),
)
async def get_run_artifact(
    scanner_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ScannerRunArtifactOut:
    scanner = await _visible_scanner(db, scanner_id, user)
    run = await db.scalar(
        select(ScannerRun).where(
            ScannerRun.id == run_id, ScannerRun.scanner_id == scanner_id
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    stored = run.artifact if isinstance(run.artifact, dict) else None
    if stored:
        return ScannerRunArtifactOut(**{**stored, "source": "stored"})

    # Runs recorded before the artifact column existed (and failed runs, which
    # the executor does not stamp) are assembled deterministically on read. No
    # LLM call and no write happen on this path — a GET stays a GET.
    artifact = await assemble_run_artifact(db, scanner, run, settings=None, use_llm=False)
    return ScannerRunArtifactOut(**{**artifact, "source": "on-read"})
