"""Heartbeat position manager — in-process code-only loop (Loop V59).

Adapted from freqtrade exit-type cadence + aeon/hermes stale-cycle posture:
deterministic evaluate → auditable decision_log → optional exit via
RiskService → OrderIntent → OrderBookService. No LLM calls.

Does not import or mutate ``app/pods/**`` (V57 charter); pod ledger is
read-only when a registry surface exists (H3).
"""

from __future__ import annotations

import logging
import time
from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    Account,
    HeartbeatDecisionLog,
    Market,
    OddsSnapshot,
    OrderOutcome,
    OrderSide,
    Order,
    OrderType,
    PaperOrder,
    Position,
)
from app.risk.rules import OrderIntent, RiskService
from app.services.heartbeat_decision import (
    HaltFlags,
    HeartbeatAction,
    HeartbeatRules,
    PositionSnapshot,
    decide,
)
from app.services.heartbeat_halts import (
    compose_halt_flags,
    evaluate_daily_loss_halts,
    evaluate_price_feed_staleness,
    halt_transition_log_rows,
)
from app.services.order_book_service import OrderBookService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TrackedPosition:
    snapshot: PositionSnapshot
    # CLOB exit wiring (None for JWT paper — decision-logged only in H2).
    account_id: UUID | None = None
    market_id: UUID | None = None
    market_slug: str | None = None


def rules_from_settings() -> HeartbeatRules:
    s = get_settings()
    return HeartbeatRules(
        time_stop_sec=float(s.heartbeat_time_stop_sec),
        adverse_move_pct=float(s.heartbeat_adverse_move_pct),
        profit_target_pct=float(s.heartbeat_profit_target_pct),
        staleness_sec=float(s.heartbeat_staleness_sec),
        tighten_adverse_pct=float(s.heartbeat_tighten_adverse_pct),
    )


def halt_flags_from_settings(*, price_feed_stale: bool = False, daily_loss_halt: bool = False) -> HaltFlags:
    s = get_settings()
    return HaltFlags(
        global_kill=bool(s.heartbeat_global_kill),
        price_feed_stale=price_feed_stale,
        daily_loss_halt=daily_loss_halt,
    )


def heartbeat_detail(summary: dict[str, Any] | None) -> str | None:
    """One-line public detail for ``GET /api/v1/system/loops``."""
    if not summary:
        return None
    parts = [
        f"scanned={summary.get('scanned', 0)}",
        f"hold={summary.get('hold', 0)}",
        f"tighten={summary.get('tighten', 0)}",
        f"exit={summary.get('exit', 0)}",
        f"emergency={summary.get('emergency', 0)}",
        f"logged={summary.get('logged', 0)}",
        f"exits_submitted={summary.get('exits_submitted', 0)}",
        f"halts_engaged={summary.get('halts_engaged', 0)}",
        f"halts_cleared={summary.get('halts_cleared', 0)}",
        f"errors={summary.get('errors', 0)}",
    ]
    return " ".join(parts)


def heartbeat_exit_idempotency_key(position_ref: str, now: datetime) -> str:
    """Stable per-position exit key, renewed only on a new UTC trading day."""
    utc_day = now.astimezone(timezone.utc).strftime("%Y%m%d") if now.tzinfo else now.strftime("%Y%m%d")
    ref_hash = sha256(position_ref.encode("utf-8")).hexdigest()[:24]
    return f"hb-exit-{ref_hash}-{utc_day}"


async def _latest_mark(
    session: AsyncSession, slug: str, outcome: str
) -> tuple[Decimal | None, datetime | None]:
    row = (
        await session.execute(
            select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
            .where(OddsSnapshot.market_slug == slug)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None, None
    implied_yes = Decimal(str(row.implied_yes))
    mark = implied_yes if outcome.lower() == "yes" else (Decimal("1") - implied_yes)
    return mark, row.captured_at


async def _load_paper_positions(session: AsyncSession) -> list[_TrackedPosition]:
    """Net-open JWT paper positions (BUY − SELL), unsettled only."""
    buy_shares = func.sum(
        case((PaperOrder.action == "BUY", PaperOrder.shares), else_=0)
    )
    sell_shares = func.sum(
        case((PaperOrder.action == "SELL", PaperOrder.shares), else_=0)
    )
    buy_cost = func.sum(case((PaperOrder.action == "BUY", PaperOrder.cost), else_=0))
    opened_at = func.min(
        case((PaperOrder.action == "BUY", PaperOrder.created_at), else_=None)
    )
    rows = (
        await session.execute(
            select(
                PaperOrder.user_id,
                PaperOrder.slug,
                PaperOrder.outcome,
                buy_shares.label("buy_shares"),
                sell_shares.label("sell_shares"),
                buy_cost.label("buy_cost"),
                opened_at.label("opened_at"),
            )
            .where(PaperOrder.settled.is_(False))
            .group_by(PaperOrder.user_id, PaperOrder.slug, PaperOrder.outcome)
        )
    ).all()

    out: list[_TrackedPosition] = []
    for row in rows:
        buys = Decimal(str(row.buy_shares or 0))
        sells = Decimal(str(row.sell_shares or 0))
        net = buys - sells
        if net <= 0 or buys <= 0:
            continue
        avg = Decimal(str(row.buy_cost or 0)) / buys
        mark, price_as_of = await _latest_mark(session, row.slug, row.outcome)
        if mark is None:
            mark = avg
            price_as_of = None
        opened = row.opened_at or datetime.now(timezone.utc)
        ref = f"paper:{row.user_id}:{row.slug}:{row.outcome}"
        out.append(
            _TrackedPosition(
                snapshot=PositionSnapshot(
                    position_ref=ref,
                    entry_price=avg,
                    mark_price=mark,
                    opened_at=opened,
                    price_as_of=price_as_of,
                    quantity=net,
                    outcome=str(row.outcome).lower(),
                    source="paper",
                )
            )
        )
    return out


async def _load_clob_positions(session: AsyncSession) -> list[_TrackedPosition]:
    rows = (
        await session.execute(
            select(Position, Market.slug)
            .join(Market, Market.id == Position.market_id)
            .where(
                Position.settled.is_(False),
                or_(Position.yes_shares > 0, Position.no_shares > 0),
            )
        )
    ).all()
    position_pairs = {(position.account_id, position.market_id) for position, _ in rows}
    opened_at_by_position: dict[tuple[UUID, UUID], datetime] = {}
    if position_pairs:
        opening_rows = (
            await session.execute(
                select(
                    Order.account_id,
                    Order.market_id,
                    func.min(Order.created_at).label("opened_at"),
                )
                .where(tuple_(Order.account_id, Order.market_id).in_(position_pairs))
                .group_by(Order.account_id, Order.market_id)
            )
        ).all()
        opened_at_by_position = {
            (row.account_id, row.market_id): row.opened_at for row in opening_rows
        }
    out: list[_TrackedPosition] = []
    for position, slug in rows:
        legs: list[tuple[str, Decimal, Decimal]] = []
        if position.yes_shares and position.yes_shares > 0:
            legs.append(("yes", position.yes_shares, position.avg_yes_cost))
        if position.no_shares and position.no_shares > 0:
            legs.append(("no", position.no_shares, position.avg_no_cost))
        for outcome, qty, entry in legs:
            mark, price_as_of = await _latest_mark(session, slug, outcome)
            if mark is None:
                mark = entry if entry and entry > 0 else Decimal("0.5")
                price_as_of = None
            entry_px = entry if entry and entry > 0 else mark
            ref = f"clob:{position.account_id}:{slug}:{outcome}"
            out.append(
                _TrackedPosition(
                    snapshot=PositionSnapshot(
                        position_ref=ref,
                        entry_price=entry_px,
                        mark_price=mark,
                    opened_at=opened_at_by_position.get((position.account_id, position.market_id)),
                        price_as_of=price_as_of,
                        quantity=qty,
                        outcome=outcome,
                        source="clob",
                    ),
                    account_id=position.account_id,
                    market_id=position.market_id,
                    market_slug=slug,
                )
            )
    return out


async def _submit_clob_exit(
    session: AsyncSession,
    tracked: _TrackedPosition,
    decision_action: str,
    *,
    now: datetime,
) -> str:
    """RiskService → OrderIntent(is_exit) → OrderBookService SELL. Returns action_taken."""
    if tracked.account_id is None or tracked.market_id is None or tracked.market_slug is None:
        return f"{decision_action}_logged"
    account = (
        await session.execute(select(Account).where(Account.id == tracked.account_id))
    ).scalar_one_or_none()
    if account is None:
        return f"{decision_action}_account_missing"

    snap = tracked.snapshot
    intent = OrderIntent(
        market_slug=tracked.market_slug,
        side="sell",
        outcome=snap.outcome,
        quantity=snap.quantity,
        price=snap.mark_price,
        predicted_prob=float(snap.mark_price),
        confidence=1.0,
        edge=0.0,
        bankroll=account.cash_balance,
        current_drawdown=0.0,
        minutes_before_start=60,
        is_exit=True,
        exit_notional_cap=snap.quantity * snap.mark_price,
    )
    ok, failures = RiskService().validate(intent)
    if not ok:
        logger.warning(
            "heartbeat exit risk rejected for %s: %s", snap.position_ref, failures
        )
        return f"{decision_action}_risk_rejected"

    outcome = OrderOutcome.YES if snap.outcome.lower() == "yes" else OrderOutcome.NO
    obs = OrderBookService(session)
    await obs.submit_order(
        tracked.market_id,
        tracked.account_id,
        OrderSide.SELL,
        outcome,
        OrderType.MARKET,
        snap.quantity,
        None,
        idempotency_key=heartbeat_exit_idempotency_key(snap.position_ref, now),
    )
    return f"{decision_action}_submitted"


async def run_heartbeat_pass(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    halts: HaltFlags | None = None,
) -> dict[str, Any]:
    """Evaluate all open paper + CLOB positions once. Returns count summary."""
    started = time.perf_counter()
    now = now or datetime.now(timezone.utc)
    rules = rules_from_settings()

    summary: dict[str, Any] = {
        "scanned": 0,
        "hold": 0,
        "tighten": 0,
        "exit": 0,
        "emergency": 0,
        "logged": 0,
        "exits_submitted": 0,
        "errors": 0,
        "halts_engaged": 0,
        "halts_cleared": 0,
    }

    try:
        tracked = await _load_paper_positions(session)
        tracked.extend(await _load_clob_positions(session))
    except Exception:
        logger.exception("heartbeat position load failed")
        summary["errors"] += 1
        return summary

    # H3: evaluate reversible emergency gates before per-position decide().
    daily_loss_refs: set[str] = set()
    price_feed_stale = False
    if halts is None:
        try:
            account_ids = list(
                {t.account_id for t in tracked if t.account_id is not None}
            )
            paper_user_ids: list[UUID] = []
            for t in tracked:
                if t.snapshot.source == "paper":
                    # position_ref = paper:<user_id>:<slug>:<outcome>
                    parts = t.snapshot.position_ref.split(":")
                    if len(parts) >= 2:
                        try:
                            paper_user_ids.append(UUID(parts[1]))
                        except ValueError:
                            pass
            paper_user_ids = list(set(paper_user_ids))
            price_feed_stale = await evaluate_price_feed_staleness(session, now=now)
            daily_loss_refs = await evaluate_daily_loss_halts(
                session,
                now=now,
                account_ids=account_ids,
                paper_user_ids=paper_user_ids,
            )
            for row in halt_transition_log_rows(now):
                action = row["action_taken"]
                if action == "halt_engaged":
                    summary["halts_engaged"] += 1
                elif action == "halt_cleared":
                    summary["halts_cleared"] += 1
                session.add(
                    HeartbeatDecisionLog(
                        position_ref=row["position_ref"],
                        rule_fired=row["rule_fired"],
                        inputs_snapshot=row["inputs_snapshot"],
                        action_taken=action,
                        latency_ms=0.0,
                    )
                )
                summary["logged"] += 1
        except Exception:
            logger.exception("heartbeat halt evaluation failed")
            summary["errors"] += 1

    for item in tracked:
        summary["scanned"] += 1
        t0 = time.perf_counter()
        try:
            pos_halts = (
                halts
                if halts is not None
                else compose_halt_flags(
                    position_ref=item.snapshot.position_ref,
                    price_feed_stale=price_feed_stale,
                    daily_loss_refs=daily_loss_refs,
                )
            )
            decision = decide(item.snapshot, rules, now=now, halts=pos_halts)
            action = decision.action
            if action is HeartbeatAction.HOLD:
                summary["hold"] += 1
                action_taken = "hold"
            elif action is HeartbeatAction.TIGHTEN:
                summary["tighten"] += 1
                action_taken = "tighten"
            elif action is HeartbeatAction.EXIT:
                summary["exit"] += 1
                if item.snapshot.source == "clob":
                    action_taken = await _submit_clob_exit(session, item, "exit", now=now)
                    if action_taken.endswith("_submitted"):
                        summary["exits_submitted"] += 1
                else:
                    # JWT paper: auditable recommendation only (no PaperOrder bypass).
                    action_taken = "exit_logged"
            else:
                # Halts and stale/missing position marks are always audit-only.
                # Never turn a global safety condition into a market SELL.
                summary["emergency"] += 1
                action_taken = "freeze_logged"

            latency_ms = (time.perf_counter() - t0) * 1000.0
            session.add(
                HeartbeatDecisionLog(
                    position_ref=item.snapshot.position_ref,
                    rule_fired=decision.rule_fired,
                    inputs_snapshot=decision.inputs,
                    action_taken=action_taken,
                    latency_ms=latency_ms,
                )
            )
            summary["logged"] += 1
        except Exception:
            logger.exception(
                "heartbeat evaluate failed for %s", item.snapshot.position_ref
            )
            summary["errors"] += 1

    try:
        await session.commit()
    except Exception:
        logger.exception("heartbeat decision_log commit failed")
        await session.rollback()
        summary["errors"] += 1

    summary["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return summary


async def heartbeat_manager_task(_: dict[str, Any] | None = None) -> dict[str, Any]:
    """ARQ/in-process entrypoint. No-op when flag off."""
    settings = get_settings()
    if not settings.heartbeat_manager_enabled:
        return {"skipped": True, "reason": "HEARTBEAT_MANAGER_ENABLED=false"}
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        return await run_heartbeat_pass(session)
