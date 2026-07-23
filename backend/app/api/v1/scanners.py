"""Scanner Studio API — compile / CRUD / run / pause (research-only)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_optional_user
from app.api.v1.launch_limits import check_user_run_allowed
from app.core.config import get_settings
from app.db.models import Scanner, ScannerRun, User
from app.db.session import get_db
from app.schemas.scanners import (
    ScannerCompileOut,
    ScannerCompileRequest,
    ScannerCreate,
    ScannerOut,
    ScannerRunOut,
    ScannerTestEmailOut,
    ScannerUpdate,
)
from app.services.scanner_compiler_service import compile_scanner_flow
from app.services.scanner_email_service import send_scanner_test_email, smtp_configured
from app.services.scanner_executor_service import run_scanner
from app.services.scanner_version_service import apply_spec_change, rollback_scanner_spec

router = APIRouter(prefix="/api/v1/scanners", tags=["scanners"])


def _enforce_run_rate(user: User) -> None:
    settings = get_settings()
    if not check_user_run_allowed(str(user.id), settings.launch_run_rate_per_hour):
        raise HTTPException(status_code=429, detail="limit reached")


def _duration_ms(run: ScannerRun) -> int | None:
    if run.started_at is None or run.finished_at is None:
        return None
    start = run.started_at
    end = run.finished_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return max(int((end - start).total_seconds() * 1000), 0)


def _repairs_from_result(result: dict | None) -> list[dict]:
    if not isinstance(result, dict):
        return []
    raw = result.get("repairs")
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def _run_out(run: ScannerRun) -> ScannerRunOut:
    repairs = _repairs_from_result(run.result if isinstance(run.result, dict) else None)
    return ScannerRunOut(
        id=run.id,
        scanner_id=run.scanner_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        checkpoint=run.checkpoint,
        result=run.result,
        error=run.error,
        duration_ms=_duration_ms(run),
        is_test=bool(run.is_test),
        repairs_count=len(repairs),
        repairs=repairs,
    )


def _interval_minutes(spec: dict) -> int:
    schedule = (spec or {}).get("schedule") or {}
    try:
        return max(int(schedule.get("interval_minutes") or 60), 0)
    except (TypeError, ValueError):
        return 60


def _next_run_at(scanner: Scanner, latest_run: ScannerRun | None) -> datetime | None:
    """Next eligible start from schedule interval + last run started_at."""
    interval = _interval_minutes(dict(scanner.spec or {}))
    if latest_run is None or latest_run.started_at is None:
        return None
    start = latest_run.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return start + timedelta(minutes=interval)


def _scanner_out(
    scanner: Scanner,
    latest_run: ScannerRun | None = None,
    *,
    last_error: str | None = None,
) -> ScannerOut:
    err = last_error
    if err is None and latest_run is not None:
        err = latest_run.error
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
        next_run_at=_next_run_at(scanner, latest_run),
        last_error=err,
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
    """Preview NL→spec compile (deterministic, optional LLM assist). Does not persist."""
    settings = get_settings()
    result = await compile_scanner_flow(body.text, settings)
    return ScannerCompileOut(
        spec=result["spec"],
        compiler=result["compiler"],
        warnings=list(result.get("warnings") or []),
    )


@router.post("/", response_model=ScannerOut, status_code=status.HTTP_201_CREATED)
async def create_scanner(
    body: ScannerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    settings = get_settings()
    owned = int(
        await db.scalar(
            select(func.count())
            .select_from(Scanner)
            .where(Scanner.owner == str(user.id))
        )
        or 0
    )
    if owned >= settings.launch_max_scanners_per_user:
        raise HTTPException(status_code=429, detail="limit reached")
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


async def _last_error_for(db: AsyncSession, scanner_id: UUID) -> str | None:
    failed = await db.scalar(
        select(ScannerRun)
        .where(ScannerRun.scanner_id == scanner_id, ScannerRun.error.is_not(None))
        .order_by(ScannerRun.started_at.desc())
        .limit(1)
    )
    return failed.error if failed is not None else None


@router.get("/{scanner_id}", response_model=ScannerOut)
async def get_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ScannerOut:
    scanner = await _get_visible_scanner(db, scanner_id, user)
    latest = await _latest_run(db, scanner.id)
    return _scanner_out(
        scanner,
        latest_run=latest,
        last_error=await _last_error_for(db, scanner.id),
    )


@router.patch("/{scanner_id}", response_model=ScannerOut)
async def update_scanner(
    scanner_id: UUID,
    body: ScannerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None or scanner.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Scanner not found")
    if body.name is not None:
        scanner.name = body.name.strip()
    if body.description is not None:
        scanner.description = body.description.strip() or None
    if body.is_public is not None:
        scanner.is_public = body.is_public
    if body.cooldown_minutes is not None:
        scanner.cooldown_minutes = body.cooldown_minutes
    if body.spec is not None:
        spec = dict(body.spec)
        if not isinstance(spec.get("steps"), list):
            raise HTTPException(status_code=400, detail="spec.steps must be a list")
        await apply_spec_change(db, scanner, spec)
    else:
        await db.flush()
        await db.refresh(scanner)
    return _scanner_out(scanner, latest_run=await _latest_run(db, scanner.id))


@router.post("/{scanner_id}/rollback", response_model=ScannerOut)
async def rollback_scanner(
    scanner_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None or scanner.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Scanner not found")
    try:
        await rollback_scanner_spec(db, scanner, version)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _scanner_out(scanner, latest_run=await _latest_run(db, scanner.id))


@router.post("/{scanner_id}/run", response_model=ScannerRunOut)
async def run_scanner_now(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerRunOut:
    _enforce_run_rate(user)
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


@router.post("/{scanner_id}/test-run", response_model=ScannerRunOut)
async def test_run_scanner_now(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerRunOut:
    """Pre-publish dry run (loop86 F-B): same pipeline, capped at 20 markets,
    flagged ``is_test``, and silent — never writes feed rows or emails.
    Never changes scanner status (publishing goes through ``/{id}/publish``).
    """
    _enforce_run_rate(user)
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    if scanner.owner != str(user.id) and not scanner.is_public:
        raise HTTPException(status_code=404, detail="Scanner not found")
    run = await run_scanner(db, scanner, test_mode=True)
    return _run_out(run)


@router.post("/{scanner_id}/test-email", response_model=ScannerTestEmailOut)
async def test_email_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerTestEmailOut:
    """Pre-publish email check (loop86 F-B): sends exactly ONE configuration
    check email via the C7 SMTP helper when SMTP is configured; otherwise
    returns HTTP 200 with ``{"sent": false, "reason": "smtp not configured"}``.
    """
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    if scanner.owner != str(user.id) and not scanner.is_public:
        raise HTTPException(status_code=404, detail="Scanner not found")
    settings = get_settings()
    if not smtp_configured(settings):
        return ScannerTestEmailOut(sent=False, reason="smtp not configured")
    sent = send_scanner_test_email(scanner, settings=settings)
    return ScannerTestEmailOut(sent=sent, reason=None if sent else "send failed")


@router.post("/{scanner_id}/publish", response_model=ScannerOut)
async def publish_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    """Publish gate (loop86 F-B): flip draft→active ONLY when at least one
    pre-publish test run (``is_test=true``, status completed/empty) exists for
    the current spec version. Otherwise HTTP 409 ``{"detail": "run a test first"}``.
    """
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None or scanner.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Scanner not found")
    if scanner.status != "draft":
        raise HTTPException(status_code=400, detail="Scanner is not a draft")

    current_version = int(scanner.version or 1)
    test_runs = (
        await db.scalars(
            select(ScannerRun).where(
                ScannerRun.scanner_id == scanner.id,
                ScannerRun.is_test.is_(True),
                ScannerRun.status.in_(("completed", "empty")),
            )
        )
    ).all()
    qualified = any(
        isinstance(r.result, dict) and r.result.get("spec_version") == current_version
        for r in test_runs
    )
    if not qualified:
        raise HTTPException(status_code=409, detail="run a test first")

    scanner.status = "active"
    await db.flush()
    await db.refresh(scanner)
    return _scanner_out(scanner, latest_run=await _latest_run(db, scanner.id))


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


@router.post("/{scanner_id}/fork", response_model=ScannerOut, status_code=status.HTTP_201_CREATED)
async def fork_scanner(
    scanner_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerOut:
    source = await _get_visible_scanner(db, scanner_id, user)
    forked = Scanner(
        name=f"{source.name} (fork)",
        description=source.description,
        owner=str(user.id),
        spec=dict(source.spec or {}),
        version=1,
        status="draft",
        is_public=False,
        cooldown_minutes=int(source.cooldown_minutes or 120),
    )
    db.add(forked)
    await db.flush()
    await db.refresh(forked)
    return _scanner_out(forked)
