"""Scanner Studio API — compile / CRUD / run / pause (research-only)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_optional_user
from app.db.models import Scanner, ScannerRun, User
from app.db.session import get_db
from app.schemas.scanners import (
    ScannerCompileOut,
    ScannerCompileRequest,
    ScannerCreate,
    ScannerOut,
    ScannerRunOut,
)
from app.services.scanner_compiler_service import compile_scanner_spec
from app.services.scanner_executor_service import run_scanner

router = APIRouter(prefix="/api/v1/scanners", tags=["scanners"])


def _run_out(run: ScannerRun) -> ScannerRunOut:
    return ScannerRunOut(
        id=run.id,
        scanner_id=run.scanner_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        checkpoint=run.checkpoint,
        result=run.result,
        error=run.error,
    )


def _scanner_out(scanner: Scanner, latest_run: ScannerRun | None = None) -> ScannerOut:
    return ScannerOut(
        id=scanner.id,
        name=scanner.name,
        description=scanner.description,
        owner=scanner.owner,
        spec=dict(scanner.spec or {}),
        version=int(scanner.version or 1),
        status=scanner.status,
        is_public=bool(scanner.is_public),
        cooldown_minutes=int(scanner.cooldown_minutes or 120),
        created_at=scanner.created_at,
        updated_at=scanner.updated_at,
        latest_run=_run_out(latest_run) if latest_run is not None else None,
    )


async def _latest_run(db: AsyncSession, scanner_id: UUID) -> ScannerRun | None:
    return await db.scalar(
        select(ScannerRun)
        .where(ScannerRun.scanner_id == scanner_id)
        .order_by(ScannerRun.started_at.desc())
        .limit(1)
    )


async def _get_visible_scanner(
    db: AsyncSession, scanner_id: UUID, user: User | None
) -> Scanner:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    owner_id = str(user.id) if user is not None else None
    if scanner.is_public or (owner_id is not None and scanner.owner == owner_id):
        return scanner
    raise HTTPException(status_code=404, detail="Scanner not found")


@router.post("/compile", response_model=ScannerCompileOut)
async def compile_scanner(body: ScannerCompileRequest) -> ScannerCompileOut:
    """Preview a deterministic NL→spec compile. Does not persist."""
    return ScannerCompileOut(spec=compile_scanner_spec(body.text))


@router.post("/", response_model=ScannerOut, status_code=status.HTTP_201_CREATED)
async def create_scanner(
    body: ScannerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    spec = dict(body.spec or {})
    if not isinstance(spec.get("steps"), list):
        raise HTTPException(status_code=400, detail="spec.steps must be a list")
    scanner = Scanner(
        name=body.name.strip(),
        description=(body.description.strip() if body.description else None),
        owner=str(user.id),
        spec=spec,
        version=1,
        status="draft",
        is_public=body.is_public,
        cooldown_minutes=body.cooldown_minutes,
    )
    db.add(scanner)
    await db.flush()
    await db.refresh(scanner)
    return _scanner_out(scanner)


@router.get("/", response_model=list[ScannerOut])
async def list_scanners(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[ScannerOut]:
    if user is None:
        clause = Scanner.is_public.is_(True)
    else:
        clause = or_(Scanner.is_public.is_(True), Scanner.owner == str(user.id))
    scanners = (
        await db.scalars(select(Scanner).where(clause).order_by(Scanner.created_at.desc()))
    ).all()
    return [_scanner_out(s) for s in scanners]


@router.get("/{scanner_id}", response_model=ScannerOut)
async def get_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ScannerOut:
    scanner = await _get_visible_scanner(db, scanner_id, user)
    latest = await _latest_run(db, scanner.id)
    return _scanner_out(scanner, latest_run=latest)


@router.post("/{scanner_id}/run", response_model=ScannerRunOut)
async def run_scanner_now(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerRunOut:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    if scanner.owner != str(user.id) and not scanner.is_public:
        raise HTTPException(status_code=404, detail="Scanner not found")
    if scanner.status == "paused":
        raise HTTPException(status_code=400, detail="Scanner is paused")
    run = await run_scanner(db, scanner)
    if scanner.status == "draft":
        scanner.status = "active"
        await db.flush()
    return _run_out(run)


@router.post("/{scanner_id}/pause", response_model=ScannerOut)
async def pause_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None or scanner.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Scanner not found")
    scanner.status = "paused"
    await db.flush()
    await db.refresh(scanner)
    return _scanner_out(scanner, latest_run=await _latest_run(db, scanner.id))


@router.post("/{scanner_id}/resume", response_model=ScannerOut)
async def resume_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None or scanner.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Scanner not found")
    scanner.status = "active"
    await db.flush()
    await db.refresh(scanner)
    return _scanner_out(scanner, latest_run=await _latest_run(db, scanner.id))


@router.get("/{scanner_id}/runs", response_model=list[ScannerRunOut])
async def list_scanner_runs(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[ScannerRunOut]:
    await _get_visible_scanner(db, scanner_id, user)
    runs = (
        await db.scalars(
            select(ScannerRun)
            .where(ScannerRun.scanner_id == scanner_id)
            .order_by(ScannerRun.started_at.desc())
            .limit(20)
        )
    ).all()
    return [_run_out(r) for r in runs]
