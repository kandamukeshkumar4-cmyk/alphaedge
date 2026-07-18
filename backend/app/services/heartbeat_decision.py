"""Heartbeat decision engine — pure hold/tighten/exit/emergency rules.

Adapted from freqtrade ``ExitType`` (ROI / stop_loss / trailing / emergency_exit)
and aeon/hermes stale-cycle posture: deterministic thresholds, no LLM, every
decision stores the inputs it saw. Order submission lives elsewhere
(RiskService → OrderIntent → OrderBookService).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class HeartbeatAction(str, Enum):
    HOLD = "hold"
    TIGHTEN = "tighten"
    EXIT = "exit"
    FREEZE = "freeze"


@dataclass(frozen=True)
class HeartbeatRules:
    """Config thresholds for one evaluate pass (from settings later)."""

    time_stop_sec: float = 86_400.0
    adverse_move_pct: float = 0.10
    profit_target_pct: float = 0.15
    staleness_sec: float = 120.0
    # When adverse move reaches this fraction of the stop, recommend tighten.
    tighten_adverse_pct: float = 0.05


@dataclass(frozen=True)
class HaltFlags:
    """Reversible halt gates. Any true freezes execution for this pass."""

    global_kill: bool = False
    price_feed_stale: bool = False
    daily_loss_halt: bool = False


@dataclass(frozen=True)
class PositionSnapshot:
    """Minimal open-position view the engine needs — no DB types."""

    position_ref: str
    entry_price: Decimal
    mark_price: Decimal
    opened_at: datetime | None
    price_as_of: datetime | None
    quantity: Decimal
    outcome: str = "yes"
    source: str = "paper"  # paper | clob | pod


@dataclass(frozen=True)
class HeartbeatDecision:
    action: HeartbeatAction
    rule_fired: str | None
    inputs: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def as_log_row(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "rule_fired": self.rule_fired,
            "inputs": dict(self.inputs),
            "reason": self.reason,
        }


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _pct_move(entry: Decimal, mark: Decimal) -> float:
    """Signed mark move vs entry as a fraction. Positive = favorable for long."""
    if entry <= 0:
        return 0.0
    return float((mark - entry) / entry)


def decide(
    position: PositionSnapshot,
    rules: HeartbeatRules,
    *,
    now: datetime,
    halts: HaltFlags | None = None,
) -> HeartbeatDecision:
    """Evaluate one open position. Pure: no I/O, no fabricated marks."""
    halts = halts or HaltFlags()
    now_u = _utc(now)
    opened = _utc(position.opened_at) if position.opened_at is not None else None
    age_sec = max(0.0, (now_u - opened).total_seconds()) if opened else None
    price_age_sec: float | None = None
    if position.price_as_of is not None:
        price_age_sec = max(0.0, (now_u - _utc(position.price_as_of)).total_seconds())

    move_pct = _pct_move(position.entry_price, position.mark_price)
    adverse_pct = max(0.0, -move_pct)
    profit_pct = max(0.0, move_pct)

    inputs: dict[str, Any] = {
        "position_ref": position.position_ref,
        "source": position.source,
        "outcome": position.outcome,
        "entry_price": str(position.entry_price),
        "mark_price": str(position.mark_price),
        "quantity": str(position.quantity),
        "opened_at": opened.isoformat().replace("+00:00", "Z") if opened else None,
        "time_stop_detail": (
            None if opened else "opened_at unknown — time_stop skipped"
        ),
        "price_as_of": (
            _utc(position.price_as_of).isoformat().replace("+00:00", "Z")
            if position.price_as_of is not None
            else None
        ),
        "age_sec": age_sec,
        "price_age_sec": price_age_sec,
        "move_pct": round(move_pct, 8),
        "adverse_pct": round(adverse_pct, 8),
        "profit_pct": round(profit_pct, 8),
        "rules": asdict(rules),
        "halts": asdict(halts),
    }

    # --- Global halt gates (highest priority; reversible, log-only) ---
    if halts.global_kill:
        return HeartbeatDecision(
            action=HeartbeatAction.FREEZE,
            rule_fired="global_kill",
            inputs=inputs,
            reason="global kill flag set",
        )
    if halts.price_feed_stale:
        return HeartbeatDecision(
            action=HeartbeatAction.FREEZE,
            rule_fired="price_feed_staleness_halt",
            inputs=inputs,
            reason="price feed marked stale — halt exits",
        )
    if halts.daily_loss_halt:
        return HeartbeatDecision(
            action=HeartbeatAction.FREEZE,
            rule_fired="daily_loss_halt",
            inputs=inputs,
            reason="daily loss halt for this pod/account",
        )

    # --- Per-position staleness kill ---
    # A stale or missing mark cannot safely price a market sell.  This is a
    # log-only freeze until a later pass receives a fresh position mark.
    if price_age_sec is None or price_age_sec > rules.staleness_sec:
        return HeartbeatDecision(
            action=HeartbeatAction.FREEZE,
            rule_fired="staleness_kill",
            inputs=inputs,
            reason=(
                "missing mark timestamp"
                if price_age_sec is None
                else f"price age {price_age_sec:.1f}s > {rules.staleness_sec}s"
            ),
        )

    # --- Time stop ---
    if age_sec is not None and age_sec >= rules.time_stop_sec:
        return HeartbeatDecision(
            action=HeartbeatAction.EXIT,
            rule_fired="time_stop",
            inputs=inputs,
            reason=f"held {age_sec:.1f}s >= time_stop {rules.time_stop_sec}s",
        )

    # --- Adverse-move stop ---
    if adverse_pct >= rules.adverse_move_pct:
        return HeartbeatDecision(
            action=HeartbeatAction.EXIT,
            rule_fired="adverse_move_stop",
            inputs=inputs,
            reason=(
                f"adverse {adverse_pct:.4%} >= stop {rules.adverse_move_pct:.4%}"
            ),
        )

    # --- Profit target ---
    if profit_pct >= rules.profit_target_pct:
        return HeartbeatDecision(
            action=HeartbeatAction.EXIT,
            rule_fired="profit_target",
            inputs=inputs,
            reason=(
                f"profit {profit_pct:.4%} >= target {rules.profit_target_pct:.4%}"
            ),
        )

    # --- Tighten (approaching stop; not yet exit) ---
    if adverse_pct >= rules.tighten_adverse_pct:
        return HeartbeatDecision(
            action=HeartbeatAction.TIGHTEN,
            rule_fired="tighten",
            inputs=inputs,
            reason=(
                f"adverse {adverse_pct:.4%} >= tighten "
                f"{rules.tighten_adverse_pct:.4%}"
            ),
        )

    return HeartbeatDecision(
        action=HeartbeatAction.HOLD,
        rule_fired=None,
        inputs=inputs,
        reason="no exit/tighten rule fired",
    )
