"""Scanner Studio API — compile / CRUD / run / pause (research-only)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_optional_user
from app.api.v1.launch_limits import check_user_run_allowed, harden_create_fields
from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import Scanner, ScannerRating, ScannerRun, User
from app.db.session import get_db
from app.schemas.scanners import (
    ClarifyQuestionOut,
    ScannerCompileOut,
    ScannerCompileRequest,
    ScannerCreate,
    ScannerFeatureRequest,
    ScannerFeaturedListOut,
    ScannerOut,
    ScannerRateRequest,
    ScannerRatingOut,
    ScannerRunOut,
    ScannerTestEmailOut,
    ScannerTestfireOut,
    ScannerTestfireRequest,
    ScannerTrendingListOut,
    ScannerTrendingOut,
    ScannerUpdate,
)
from app.services.marketplace_rating_service import upsert_scanner_rating
from app.services.marketplace_trending_service import (
    compute_trending_score,
    recent_window_start,
    sort_trending_items,
)
from app.services.scanner_compiler_service import (
    compile_scanner_conversational,
    get_compile_draft,
)
from app.services.scanner_email_service import send_scanner_test_email, smtp_configured
from app.services.scanner_executor_service import run_scanner
from app.services.scanner_version_service import apply_spec_change, rollback_scanner_spec

router = APIRouter(prefix="/api/v1/scanners", tags=["scanners"])

# Scratch owner for compile-testfire scanners. Hidden from list/trending
# (is_public=False and never matches a real user id). Exists only because
# ScannerRun.scanner_id is a required FK — not a published user scanner.
_COMPILE_DRAFT_OWNER = "__compile_draft__"


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
        is_featured=bool(scanner.is_featured),
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
    """Conversational NL→spec compile (loop116).

    Deterministic clarification decisions (schedule / threshold / universe /
    delivery). Optional LLM planner may phrase the base spec but never silently
    invents thresholds — gaps become questions (max 3/round, max 2 rounds then
    best-effort ready). Drafts are process-local scratch keyed by draft_id.
    """
    settings = get_settings()
    answers = [
        {"question_id": a.question_id, "answer": a.answer}
        for a in (body.answers or [])
    ]
    result = await compile_scanner_conversational(
        prompt=body.resolved_prompt(),
        answers=answers,
        draft_id=body.draft_id,
        settings=settings,
    )
    if result.get("error") == "draft_not_found":
        raise HTTPException(status_code=404, detail="draft not found")

    status = str(result.get("status") or "ready")
    if status == "needs_clarification":
        questions = [
            ClarifyQuestionOut(**q) for q in (result.get("questions") or [])
        ]
        partial = dict(result.get("spec_partial") or {})
        return ScannerCompileOut(
            status="needs_clarification",
            draft_id=str(result["draft_id"]),
            spec=partial,  # soft back-compat for clients that only read spec
            spec_partial=partial,
            questions=questions,
            compiler=result.get("compiler") or "deterministic",
            warnings=list(result.get("warnings") or []),
        )

    return ScannerCompileOut(
        status="ready",
        draft_id=str(result["draft_id"]),
        spec=dict(result.get("spec") or {}),
        spec_partial=None,
        questions=[],
        compiler=result.get("compiler") or "deterministic",
        warnings=list(result.get("warnings") or []),
    )


@router.post("/compile/testfire", response_model=ScannerTestfireOut)
async def testfire_compile_draft(
    body: ScannerTestfireRequest,
    db: AsyncSession = Depends(get_db),
) -> ScannerTestfireOut:
    """Dry-run a ready compile draft via the real executor (is_test=true).

    Does not publish a user scanner. A scratch Scanner row with owner
    ``__compile_draft__`` is created solely to satisfy ScannerRun's FK; it is
    never public and never appears in the owner's list. The run is persisted
    with ``is_test=true`` and silent (no feed rows / no email).
    """
    draft = get_compile_draft(body.draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    if str(draft.get("status") or "") != "ready":
        raise HTTPException(status_code=409, detail="draft not ready")
    spec = dict(draft.get("spec") or {})
    if not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise HTTPException(status_code=400, detail="draft has no steps")

    scratch = Scanner(
        name=str(spec.get("name") or "Compile draft")[:120],
        description="compile-testfire scratch (not a published scanner)",
        owner=_COMPILE_DRAFT_OWNER,
        spec=spec,
        version=1,
        status="draft",
        is_public=False,
        cooldown_minutes=int(
            (spec.get("delivery") or {}).get("cooldown_minutes") or 120
        )
        if isinstance(spec.get("delivery"), dict)
        else 120,
    )
    db.add(scratch)
    await db.flush()
    run = await run_scanner(db, scratch, test_mode=True)
    result = run.result if isinstance(run.result, dict) else {}
    candidates = result.get("candidates") if isinstance(result.get("candidates"), list) else []
    top_pick = result.get("top_pick") if isinstance(result.get("top_pick"), dict) else None
    top_matches: list[dict] = []
    if top_pick is not None:
        top_matches.append(top_pick)
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        if top_pick is not None and cand.get("market_slug") == top_pick.get("market_slug"):
            continue
        top_matches.append(cand)
        if len(top_matches) >= 5:
            break
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    summary = {
        "status": run.status,
        "is_test": bool(run.is_test),
        "test_mode": bool(result.get("test_mode")),
        "counts": counts,
        "error": run.error,
    }
    return ScannerTestfireOut(
        draft_id=body.draft_id,
        run=_run_out(run),
        summary=summary,
        top_matches=top_matches,
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
    name, description = harden_create_fields(
        name=body.name,
        description=body.description,
        payload=spec,
        steps=spec.get("steps"),
    )
    scanner = Scanner(
        name=name,
        description=description,
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


@router.get("/trending", response_model=ScannerTrendingListOut)
async def trending_scanners(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> ScannerTrendingListOut:
    """Rank public scanners by 7d run count + avg_rating. Deterministic."""
    # Reference time is injected once here; pure score fn never calls now().
    now = datetime.now(UTC)
    window_start = recent_window_start(now)

    scanners = (
        await db.scalars(select(Scanner).where(Scanner.is_public.is_(True)))
    ).all()
    if not scanners:
        return ScannerTrendingListOut(items=[])

    scanner_ids = [s.id for s in scanners]

    rating_rows = (
        await db.execute(
            select(
                ScannerRating.ref_id,
                func.avg(ScannerRating.stars),
                func.count(),
            )
            .where(ScannerRating.ref_id.in_(scanner_ids))
            .group_by(ScannerRating.ref_id)
        )
    ).all()
    rating_map = {
        row[0]: (float(row[1] or 0.0), int(row[2] or 0)) for row in rating_rows
    }

    recent_rows = (
        await db.execute(
            select(ScannerRun.scanner_id, func.count())
            .where(
                ScannerRun.scanner_id.in_(scanner_ids),
                ScannerRun.started_at >= window_start,
                ScannerRun.started_at <= now,
            )
            .group_by(ScannerRun.scanner_id)
        )
    ).all()
    recent_map = {row[0]: int(row[1] or 0) for row in recent_rows}

    total_rows = (
        await db.execute(
            select(ScannerRun.scanner_id, func.count())
            .where(ScannerRun.scanner_id.in_(scanner_ids))
            .group_by(ScannerRun.scanner_id)
        )
    ).all()
    total_map = {row[0]: int(row[1] or 0) for row in total_rows}

    built: list[dict] = []
    for scanner in scanners:
        avg_rating, rating_count = rating_map.get(scanner.id, (0.0, 0))
        recent = recent_map.get(scanner.id, 0)
        run_count = total_map.get(scanner.id, 0)
        score = compute_trending_score(
            recent_run_count=recent,
            avg_rating=avg_rating,
            run_count=run_count,
        )
        base = _scanner_out(scanner).model_dump()
        base.update(
            {
                "avg_rating": avg_rating,
                "rating_count": rating_count,
                "run_count": run_count,
                "trending_score": score,
                "name": scanner.name,
            }
        )
        built.append(base)

    ranked = sort_trending_items(built, limit=limit)
    return ScannerTrendingListOut(
        items=[ScannerTrendingOut(**row) for row in ranked]
    )


@router.get("/featured", response_model=ScannerFeaturedListOut)
async def featured_scanners(
    db: AsyncSession = Depends(get_db),
) -> ScannerFeaturedListOut:
    scanners = (
        await db.scalars(
            select(Scanner)
            .where(Scanner.is_featured.is_(True))
            .order_by(Scanner.name.asc())
        )
    ).all()
    return ScannerFeaturedListOut(items=[_scanner_out(s) for s in scanners])


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


@router.post("/{scanner_id}/rate", response_model=ScannerRatingOut)
async def rate_scanner(
    scanner_id: UUID,
    body: ScannerRateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerRatingOut:
    scanner = await _get_visible_scanner(db, scanner_id, user)
    avg, count, my_stars = await upsert_scanner_rating(
        db, user=str(user.id), ref_id=scanner.id, stars=body.stars
    )
    return ScannerRatingOut(avg=avg, count=count, my_stars=my_stars)


@router.post("/{scanner_id}/feature", response_model=ScannerOut)
async def feature_scanner(
    scanner_id: UUID,
    body: ScannerFeatureRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin_api_key),
) -> ScannerOut:
    scanner = await db.scalar(select(Scanner).where(Scanner.id == scanner_id))
    if scanner is None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    scanner.is_featured = bool(body.is_featured)
    await db.flush()
    await db.refresh(scanner)
    return _scanner_out(scanner, latest_run=await _latest_run(db, scanner.id))


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
