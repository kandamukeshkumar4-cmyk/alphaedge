"""L03 — per-user notification preferences (STORED + read in-app only).

Routes:
    GET  /api/v1/notify/prefs   the caller's enabled alert families
    PUT  /api/v1/notify/prefs   replace the caller's enabled alert families

AUTHED (JWT — 401 when anonymous). Per-user opt-in set of alert families,
matching the digest/feed family keys (``news:mispricing``, ``anomaly:unusual_
flow``, ``delta:*``, ``screener:*``, ``arb``). Default when a user has NO stored
row: ALL families on.

HARD GUARDRAIL: this is a preference STORE only. There is NO external delivery
of any kind — no email, SMS, or webhook. Prefs are stored and read in-app to
decide which alert families a user surfaces; nothing here sends a notification.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import NotifyPref, User
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/notify", tags=["notify"])

# Canonical alert families (same keys the L02 digest reports). The stored prefs
# and the PUT validator are keyed off this single source of truth.
ALERT_FAMILIES: tuple[str, ...] = (
    "news:mispricing",
    "anomaly:unusual_flow",
    "delta:*",
    "screener:*",
    "arb",
)

NOTIFY_PREFS_DISCLAIMER = (
    "Notification preferences are STORED and applied in-app only. There is NO "
    "external delivery (no email/SMS/webhook). Simulated funds only."
)


class NotifyPrefsResponse(BaseModel):
    families: dict[str, bool]
    enabled: list[str]
    all_families: list[str]
    source: str  # "default" (no stored row) | "stored"
    paper_trading_only: bool
    disclaimer: str


class NotifyPrefsUpdate(BaseModel):
    families: list[str]

    @field_validator("families")
    @classmethod
    def _validate_families(cls, value: list[str]) -> list[str]:
        unknown = [f for f in value if f not in ALERT_FAMILIES]
        if unknown:
            raise ValueError(
                f"unknown alert families: {unknown}; valid: {list(ALERT_FAMILIES)}"
            )
        # Dedupe while preserving membership; canonical order applied on read.
        return list(dict.fromkeys(value))


def _shape(enabled: list[str], *, source: str) -> NotifyPrefsResponse:
    enabled_set = set(enabled)
    return NotifyPrefsResponse(
        families={f: (f in enabled_set) for f in ALERT_FAMILIES},
        enabled=[f for f in ALERT_FAMILIES if f in enabled_set],
        all_families=list(ALERT_FAMILIES),
        source=source,
        paper_trading_only=True,
        disclaimer=NOTIFY_PREFS_DISCLAIMER,
    )


async def _get_row(db: AsyncSession, user_id: Any) -> NotifyPref | None:
    return await db.scalar(
        select(NotifyPref).where(NotifyPref.user_id == user_id)
    )


@router.get("/prefs", response_model=NotifyPrefsResponse)
async def get_notify_prefs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotifyPrefsResponse:
    """The caller's enabled alert families. Default (no stored row) = all on."""
    row = await _get_row(db, current_user.id)
    if row is None:
        return _shape(list(ALERT_FAMILIES), source="default")
    stored = [f for f in (row.families or []) if f in ALERT_FAMILIES]
    return _shape(stored, source="stored")


@router.put("/prefs", response_model=NotifyPrefsResponse)
async def put_notify_prefs(
    update: NotifyPrefsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotifyPrefsResponse:
    """Replace the caller's enabled alert families (upsert). Unknown family names
    are rejected (422) by the request validator. STORED only — no external send."""
    enabled = [f for f in ALERT_FAMILIES if f in set(update.families)]
    row = await _get_row(db, current_user.id)
    if row is None:
        row = NotifyPref(user_id=current_user.id, families=enabled)
        db.add(row)
    else:
        row.families = enabled
    await db.commit()
    return _shape(enabled, source="stored")
