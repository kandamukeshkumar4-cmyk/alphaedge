"""Fixture tests for the pure heartbeat decision engine (Loop V59 H1)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.heartbeat_decision import (
    HaltFlags,
    HeartbeatAction,
    HeartbeatRules,
    PositionSnapshot,
    decide,
)

_NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
_RULES = HeartbeatRules(
    time_stop_sec=3600.0,
    adverse_move_pct=0.10,
    profit_target_pct=0.15,
    staleness_sec=120.0,
    tighten_adverse_pct=0.05,
)


def _pos(
    *,
    entry: str = "0.50",
    mark: str = "0.50",
    age_sec: float = 60.0,
    price_age_sec: float = 10.0,
) -> PositionSnapshot:
    return PositionSnapshot(
        position_ref="paper:user:nba-2025-01-15-lal-bos:yes",
        entry_price=Decimal(entry),
        mark_price=Decimal(mark),
        opened_at=_NOW - timedelta(seconds=age_sec),
        price_as_of=_NOW - timedelta(seconds=price_age_sec),
        quantity=Decimal("10"),
        outcome="yes",
        source="paper",
    )


def test_hold_when_flat_and_fresh():
    d = decide(_pos(), _RULES, now=_NOW)
    assert d.action is HeartbeatAction.HOLD
    assert d.rule_fired is None
    assert d.inputs["entry_price"] == "0.50"
    assert d.inputs["mark_price"] == "0.50"


def test_time_stop_exits():
    d = decide(_pos(age_sec=3600.0), _RULES, now=_NOW)
    assert d.action is HeartbeatAction.EXIT
    assert d.rule_fired == "time_stop"
    assert d.inputs["age_sec"] == 3600.0


def test_unknown_opened_at_skips_time_stop_with_an_honest_detail():
    pos = _pos(age_sec=3600.0)
    d = decide(
        PositionSnapshot(
            **{**pos.__dict__, "opened_at": None},
        ),
        _RULES,
        now=_NOW,
    )
    assert d.action is HeartbeatAction.HOLD
    assert d.inputs["opened_at"] is None
    assert d.inputs["time_stop_detail"] == "opened_at unknown — time_stop skipped"


def test_adverse_move_stop_exits():
    # 0.50 -> 0.44 = -12% adverse
    d = decide(_pos(mark="0.44"), _RULES, now=_NOW)
    assert d.action is HeartbeatAction.EXIT
    assert d.rule_fired == "adverse_move_stop"
    assert d.inputs["adverse_pct"] >= 0.10


def test_profit_target_exits():
    # 0.50 -> 0.58 = +16%
    d = decide(_pos(mark="0.58"), _RULES, now=_NOW)
    assert d.action is HeartbeatAction.EXIT
    assert d.rule_fired == "profit_target"


def test_tighten_before_full_stop():
    # 0.50 -> 0.47 = -6% (between tighten 5% and stop 10%)
    d = decide(_pos(mark="0.47"), _RULES, now=_NOW)
    assert d.action is HeartbeatAction.TIGHTEN
    assert d.rule_fired == "tighten"


def test_staleness_kill_when_price_old():
    d = decide(_pos(price_age_sec=121.0), _RULES, now=_NOW)
    assert d.action is HeartbeatAction.FREEZE
    assert d.rule_fired == "staleness_kill"


def test_staleness_kill_when_price_as_of_missing():
    pos = PositionSnapshot(
        position_ref="clob:acct:mkt:yes",
        entry_price=Decimal("0.40"),
        mark_price=Decimal("0.41"),
        opened_at=_NOW - timedelta(seconds=30),
        price_as_of=None,
        quantity=Decimal("5"),
    )
    d = decide(pos, _RULES, now=_NOW)
    assert d.action is HeartbeatAction.FREEZE
    assert d.rule_fired == "staleness_kill"
    assert d.inputs["price_as_of"] is None


def test_global_kill_beats_profit():
    d = decide(
        _pos(mark="0.58"),
        _RULES,
        now=_NOW,
        halts=HaltFlags(global_kill=True),
    )
    assert d.action is HeartbeatAction.FREEZE
    assert d.rule_fired == "global_kill"


def test_price_feed_halt_and_daily_loss_halt():
    d1 = decide(
        _pos(),
        _RULES,
        now=_NOW,
        halts=HaltFlags(price_feed_stale=True),
    )
    assert d1.rule_fired == "price_feed_staleness_halt"
    assert d1.action is HeartbeatAction.FREEZE

    d2 = decide(
        _pos(),
        _RULES,
        now=_NOW,
        halts=HaltFlags(daily_loss_halt=True),
    )
    assert d2.rule_fired == "daily_loss_halt"
    assert d2.action is HeartbeatAction.FREEZE


def test_halts_freeze_even_when_a_profit_exit_would_otherwise_fire():
    for halts in (
        HaltFlags(global_kill=True),
        HaltFlags(price_feed_stale=True),
        HaltFlags(daily_loss_halt=True),
    ):
        d = decide(_pos(mark="0.58"), _RULES, now=_NOW, halts=halts)
        assert d.action is HeartbeatAction.FREEZE


def test_decision_inputs_are_auditable_snapshot():
    d = decide(_pos(mark="0.51"), _RULES, now=_NOW)
    assert "rules" in d.inputs
    assert "halts" in d.inputs
    row = d.as_log_row()
    assert row["action"] == "hold"
    assert row["inputs"]["position_ref"].startswith("paper:")


def test_priority_adverse_beats_tighten():
    # -12% hits stop, not merely tighten
    d = decide(_pos(mark="0.44"), _RULES, now=_NOW)
    assert d.rule_fired == "adverse_move_stop"
