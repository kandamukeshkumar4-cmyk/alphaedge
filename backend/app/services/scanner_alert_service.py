"""Scanner fired alerts for the signals/toast feed (research-only).

Writes ``scanner:fired`` SignalEvent rows via SignalsService. Never places
orders or calls RiskService / OrderBookService.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Scanner, ScannerRun, SignalEvent
from app.services.signals_service import SignalsService

logger = logging.getLogger(__name__)

SCANNER_FIRED_SIGNAL_TYPE = "scanner:fired"
SCANNER_FAILING_SIGNAL_TYPE = "scanner:failing"


def _aligned_count(result: dict[str, Any] | None) -> int:
    if not isinstance(result, dict):
        return 0
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    try:
        return int(counts.get("aligned") or 0)
    except (TypeError, ValueError):
        return 0


async def _cooldown_hit(
    db: AsyncSession,
    *,
    scanner_id: str,
    market_slug: str,
    cooldown_minutes: int,
    now: datetime,
) -> bool:
    if cooldown_minutes <= 0:
        return False
    since = now - timedelta(minutes=cooldown_minutes)
    rows = (
        await db.scalars(
            select(SignalEvent)
            .where(
                SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE,
                SignalEvent.market_id == market_slug,
                SignalEvent.created_at >= since,
            )
            .order_by(SignalEvent.created_at.desc())
            .limit(20)
        )
    ).all()
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        if str(payload.get("scanner_id") or "") == scanner_id:
            return True
    return False


async def record_scanner_fired_alert(
    db: AsyncSession,
    scanner: Scanner,
    run: ScannerRun,
    *,
    now: datetime | None = None,
) -> SignalEvent | None:
    """Persist one ``scanner:fired`` feed row for the top aligned pick.

    Skips when the run has no aligned candidates, or when the same
    scanner+market already alerted within ``scanner.cooldown_minutes``.
    """
    result = run.result if isinstance(run.result, dict) else None
    if _aligned_count(result) < 1:
        return None

    top = result.get("top_pick") if result else None
    if not isinstance(top, dict):
        return None
    market_slug = str(top.get("market_slug") or "").strip()
    if not market_slug:
        return None

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    scanner_id = str(scanner.id)
    cooldown = int(scanner.cooldown_minutes or 0)
    if await _cooldown_hit(
        db,
        scanner_id=scanner_id,
        market_slug=market_slug,
        cooldown_minutes=cooldown,
        now=current,
    ):
        return None

    pick_title = str(top.get("title") or market_slug)
    title = f"{scanner.name}: {pick_title}"
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    payload: dict[str, Any] = {
        "title": title,
        "scanner_name": scanner.name,
        "scanner_id": scanner_id,
        "run_id": str(run.id),
        "market_slug": market_slug,
        "top_pick": top,
        "counts": counts,
    }

    svc = SignalsService(db)
    await svc._persist_signal(
        SCANNER_FIRED_SIGNAL_TYPE,
        "scanner",
        market_slug[:128],
        True,
        payload,
    )
    try:
        from app.services.scanner_email_service import maybe_email_scanner_fired

        maybe_email_scanner_fired(scanner, run)
    except Exception:  # noqa: BLE001 — email must never break the alert path
        logger.warning("scanner fired email hook failed", exc_info=True)
    try:
        from app.services.notification_producers import notify_scanner_fired

        await notify_scanner_fired(
            scanner=scanner,
            run=run,
            market_slug=market_slug,
            title=title,
            session=db,
        )
    except Exception:  # noqa: BLE001 — in-app fan-out must never break alerts
        logger.warning("scanner fired notification hook failed", exc_info=True)
    event = await db.scalar(
        select(SignalEvent)
        .where(
            SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE,
            SignalEvent.market_id == market_slug[:128],
        )
        .order_by(SignalEvent.created_at.desc())
        .limit(1)
    )
    return event


async def record_scanner_failing_alert(
    db: AsyncSession,
    scanner: Scanner,
    run: ScannerRun,
) -> SignalEvent | None:
    """Persist one ``scanner:failing`` feed row after repeated failures."""
    scanner_id = str(scanner.id)
    market_id = f"scanner:{scanner_id}"[:128]
    payload: dict[str, Any] = {
        "title": f"{scanner.name}: repeated failures",
        "scanner_name": scanner.name,
        "scanner_id": scanner_id,
        "run_id": str(run.id),
        "error": run.error,
        "status": scanner.status,
    }
    svc = SignalsService(db)
    await svc._persist_signal(
        SCANNER_FAILING_SIGNAL_TYPE,
        "scanner",
        market_id,
        True,
        payload,
    )
    event = await db.scalar(
        select(SignalEvent)
        .where(
            SignalEvent.signal_type == SCANNER_FAILING_SIGNAL_TYPE,
            SignalEvent.market_id == market_id,
        )
        .order_by(SignalEvent.created_at.desc())
        .limit(1)
    )
    return event
