"""Loop V59 H3 — reversible emergency halt evaluators.

Price-feed staleness, daily-loss (pod ledger read-only when present; else
per-account ledger / paper realized PnL), and global kill. Halts are
in-process + settings-backed: clearing the condition (or flipping
HEARTBEAT_GLOBAL_KILL=false) releases them — no permanent latch.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Account, LedgerEntry, Market, OddsSnapshot, PaperOrder, Position, User
from app.services.heartbeat_decision import HaltFlags

logger = logging.getLogger(__name__)


@dataclass
class HaltState:
    """In-process reversible halt latches (cleared when conditions clear)."""

    price_feed_stale: bool = False
    daily_loss_accounts: set[str] = field(default_factory=set)
    last_eval: dict[str, Any] = field(default_factory=dict)


_lock = threading.Lock()
_state = HaltState()


def get_halt_state() -> HaltState:
    with _lock:
        return HaltState(
            price_feed_stale=_state.price_feed_stale,
            daily_loss_accounts=set(_state.daily_loss_accounts),
            last_eval=dict(_state.last_eval),
        )


def reset_halt_state() -> None:
    """Test helper — clear all in-process halt latches."""
    with _lock:
        _state.price_feed_stale = False
        _state.daily_loss_accounts.clear()
        _state.last_eval.clear()


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


async def evaluate_price_feed_staleness(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    stale_after_sec: float | None = None,
) -> bool:
    """True when the newest OddsSnapshot is older than the threshold.

    Empty odds table → not stale (honest cold start; per-position staleness_kill
    still covers missing marks). Reversible: fresh ticks clear the latch.
    """
    now = _utc(now or datetime.now(timezone.utc))
    settings = get_settings()
    threshold = (
        float(stale_after_sec)
        if stale_after_sec is not None
        else float(settings.heartbeat_staleness_sec)
    )
    newest = (
        await session.execute(select(func.max(OddsSnapshot.captured_at)))
    ).scalar_one_or_none()
    if newest is None:
        stale = False
    else:
        newest_u = _utc(newest)
        age = (now - newest_u).total_seconds()
        stale = age > threshold

    with _lock:
        prev = _state.price_feed_stale
        _state.price_feed_stale = stale
        _state.last_eval["price_feed"] = {
            "stale": stale,
            "threshold_sec": threshold,
            "newest_captured_at": newest.isoformat() if newest else None,
            "cleared": prev and not stale,
            "engaged": (not prev) and stale,
        }
        engaged = _state.last_eval["price_feed"]["engaged"]
        cleared = _state.last_eval["price_feed"]["cleared"]

    if engaged:
        logger.warning("heartbeat price-feed staleness halt ENGAGED")
    if cleared:
        logger.info("heartbeat price-feed staleness halt CLEARED")
    return stale


def _try_pod_daily_pnl(pod_ref: str) -> Decimal | None:
    """Read-only pod ledger via optional V57 registry. Never imports pods internals."""
    try:
        from app.pods import registry as pods_registry  # type: ignore[attr-defined]
    except ImportError:
        return None
    reader = getattr(pods_registry, "read_daily_pnl", None)
    if reader is None:
        return None
    try:
        value = reader(pod_ref)
    except Exception:  # noqa: BLE001 — registry must not break heartbeat
        logger.exception("pod daily pnl read failed for %s", pod_ref)
        return None
    if value is None:
        return None
    return Decimal(str(value))


async def _account_daily_pnl(session: AsyncSession, account_id: UUID, day_start: datetime) -> Decimal:
    """Sum ledger amounts for account since day_start (read-only)."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.created_at >= day_start,
            )
        )
    ).scalar_one()
    return Decimal(str(total))


async def _paper_user_daily_realized(
    session: AsyncSession, user_id: UUID, day_start: datetime
) -> Decimal:
    total = (
        await session.execute(
            select(func.coalesce(func.sum(PaperOrder.realized_pnl), 0)).where(
                PaperOrder.user_id == user_id,
                PaperOrder.action == "SELL",
                PaperOrder.created_at >= day_start,
                PaperOrder.realized_pnl.is_not(None),
            )
        )
    ).scalar_one()
    return Decimal(str(total))


async def _account_equity(
    session: AsyncSession, account_id: UUID, now: datetime, stale_after_sec: float
) -> Decimal | None:
    """Return cash plus fresh marked open-position value, or None when unknown."""
    cash = await session.scalar(select(Account.cash_balance).where(Account.id == account_id))
    if cash is None:
        return None
    latest = (
        select(
            OddsSnapshot.market_slug.label("market_slug"),
            OddsSnapshot.implied_yes.label("implied_yes"),
            OddsSnapshot.captured_at.label("captured_at"),
            func.row_number()
            .over(
                partition_by=OddsSnapshot.market_slug,
                order_by=OddsSnapshot.captured_at.desc(),
            )
            .label("rank"),
        )
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                Position.yes_shares,
                Position.no_shares,
                latest.c.implied_yes,
                latest.c.captured_at,
            )
            .join(Market, Market.id == Position.market_id)
            .outerjoin(
                latest,
                and_(Market.slug == latest.c.market_slug, latest.c.rank == 1),
            )
            .where(
                Position.account_id == account_id,
                Position.settled.is_(False),
            )
        )
    ).all()
    positions_value = Decimal("0")
    for row in rows:
        has_position = (
            Decimal(str(row.yes_shares or 0)) > 0
            or Decimal(str(row.no_shares or 0)) > 0
        )
        if not has_position:
            continue
        if row.implied_yes is None or row.captured_at is None:
            return None
        age_sec = (now - _utc(row.captured_at)).total_seconds()
        if age_sec < 0 or age_sec > stale_after_sec:
            return None
        implied_yes = Decimal(str(row.implied_yes))
        positions_value += Decimal(str(row.yes_shares or 0)) * implied_yes
        positions_value += Decimal(str(row.no_shares or 0)) * (Decimal("1") - implied_yes)
    equity = Decimal(str(cash)) + positions_value
    return equity if equity > 0 else None


async def _paper_user_starting_equity(
    session: AsyncSession, user_id: UUID
) -> Decimal | None:
    balance = await session.scalar(select(User.paper_balance).where(User.id == user_id))
    if balance is None:
        return None
    equity = Decimal(str(balance))
    return equity if equity > 0 else None


async def evaluate_daily_loss_halts(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    account_ids: list[UUID] | None = None,
    paper_user_ids: list[UUID] | None = None,
    pod_refs: list[str] | None = None,
) -> set[str]:
    """Return refs currently under daily-loss halt. Reversible when PnL recovers."""
    now = _utc(now or datetime.now(timezone.utc))
    settings = get_settings()
    halt_pct = Decimal(str(settings.heartbeat_daily_loss_halt_pct))
    stale_after_sec = float(settings.heartbeat_staleness_sec)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    halted: set[str] = set()
    details: list[dict[str, Any]] = []

    for pod_ref in pod_refs or []:
        pnl = _try_pod_daily_pnl(pod_ref)
        if pnl is None:
            continue
        # Halt when daily PnL <= -halt_pct of a unit bankroll (1.0) — pods report
        # fraction already when registry present; treat absolute fraction.
        loss_frac = float(-pnl) if pnl < 0 else 0.0
        is_halt = loss_frac >= float(halt_pct)
        ref = f"pod:{pod_ref}"
        details.append({"ref": ref, "pnl": str(pnl), "halt": is_halt})
        if is_halt:
            halted.add(ref)

    for account_id in account_ids or []:
        pnl = await _account_daily_pnl(session, account_id, day_start)
        equity = await _account_equity(session, account_id, now, stale_after_sec)
        ref = f"clob:{account_id}"
        if equity is None:
            details.append({"ref": ref, "pnl": str(pnl), "valuation": "unknown", "halt": True})
            halted.add(ref)
            continue
        loss_frac = float((-pnl) / equity) if pnl < 0 else 0.0
        is_halt = loss_frac >= float(halt_pct)
        details.append({"ref": ref, "pnl": str(pnl), "equity": str(equity), "loss_frac": loss_frac, "halt": is_halt})
        if is_halt:
            halted.add(ref)

    for user_id in paper_user_ids or []:
        pnl = await _paper_user_daily_realized(session, user_id, day_start)
        equity = await _paper_user_starting_equity(session, user_id)
        ref = f"paper:{user_id}"
        if equity is None:
            details.append({"ref": ref, "pnl": str(pnl), "valuation": "unknown", "halt": True})
            halted.add(ref)
            continue
        loss_frac = float((-pnl) / equity) if pnl < 0 else 0.0
        is_halt = loss_frac >= float(halt_pct)
        details.append({"ref": ref, "pnl": str(pnl), "equity": str(equity), "loss_frac": loss_frac, "halt": is_halt})
        if is_halt:
            halted.add(ref)

    with _lock:
        prev = set(_state.daily_loss_accounts)
        _state.daily_loss_accounts = set(halted)
        _state.last_eval["daily_loss"] = {
            "halted": sorted(halted),
            "threshold_pct": float(halt_pct),
            "details": details,
            "engaged": sorted(halted - prev),
            "cleared": sorted(prev - halted),
        }
        engaged = _state.last_eval["daily_loss"]["engaged"]
        cleared = _state.last_eval["daily_loss"]["cleared"]

    for ref in engaged:
        logger.warning("heartbeat daily-loss halt ENGAGED for %s", ref)
    for ref in cleared:
        logger.info("heartbeat daily-loss halt CLEARED for %s", ref)
    return halted


def compose_halt_flags(
    *,
    position_ref: str,
    price_feed_stale: bool,
    daily_loss_refs: set[str],
) -> HaltFlags:
    """Map global + per-ref halt state into decision HaltFlags."""
    settings = get_settings()
    daily = False
    # Match paper:<uuid>:... / clob:<uuid>:... prefix against halted refs.
    for ref in daily_loss_refs:
        if position_ref == ref or position_ref.startswith(ref + ":"):
            daily = True
            break
    return HaltFlags(
        global_kill=bool(settings.heartbeat_global_kill),
        price_feed_stale=price_feed_stale,
        daily_loss_halt=daily,
    )


def halt_transition_log_rows(now: datetime | None = None) -> list[dict[str, Any]]:
    """Build decision_log payloads for halt engage/clear events (auditable)."""
    now = _utc(now or datetime.now(timezone.utc))
    state = get_halt_state()
    rows: list[dict[str, Any]] = []
    pf = state.last_eval.get("price_feed") or {}
    if pf.get("engaged"):
        rows.append(
            {
                "position_ref": "halt:price_feed",
                "rule_fired": "price_feed_staleness_halt",
                "action_taken": "halt_engaged",
                "inputs_snapshot": pf,
            }
        )
    if pf.get("cleared"):
        rows.append(
            {
                "position_ref": "halt:price_feed",
                "rule_fired": "price_feed_staleness_halt",
                "action_taken": "halt_cleared",
                "inputs_snapshot": pf,
            }
        )
    dl = state.last_eval.get("daily_loss") or {}
    for ref in dl.get("engaged") or []:
        rows.append(
            {
                "position_ref": f"halt:daily_loss:{ref}",
                "rule_fired": "daily_loss_halt",
                "action_taken": "halt_engaged",
                "inputs_snapshot": {"ref": ref, **{k: dl.get(k) for k in ("threshold_pct",)}},
            }
        )
    for ref in dl.get("cleared") or []:
        rows.append(
            {
                "position_ref": f"halt:daily_loss:{ref}",
                "rule_fired": "daily_loss_halt",
                "action_taken": "halt_cleared",
                "inputs_snapshot": {"ref": ref, **{k: dl.get(k) for k in ("threshold_pct",)}},
            }
        )
    if get_settings().heartbeat_global_kill:
        rows.append(
            {
                "position_ref": "halt:global_kill",
                "rule_fired": "global_kill",
                "action_taken": "halt_active",
                "inputs_snapshot": {"heartbeat_global_kill": True},
            }
        )
    # stamp — unused except for callers that want created_at alignment
    for row in rows:
        row.setdefault("created_at", now)
    return rows
