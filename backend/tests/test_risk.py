from decimal import Decimal

from app.risk.rules import OrderIntent, RiskService


def test_risk_rejects_low_edge():
    intent = OrderIntent(
        market_slug="nba-2025-01-15-lal-bos",
        side="buy",
        outcome="yes",
        quantity=Decimal("10"),
        price=Decimal("0.55"),
        predicted_prob=0.56,
        confidence=0.8,
        edge=0.01,
        bankroll=Decimal("10000"),
        current_drawdown=0.0,
        minutes_before_start=30,
    )
    ok, failures = RiskService().validate(intent)
    assert not ok
    assert any("edge" in f for f in failures)


def test_risk_accepts_valid_intent():
    intent = OrderIntent(
        market_slug="nba-2025-01-15-lal-bos",
        side="buy",
        outcome="yes",
        quantity=Decimal("10"),
        price=Decimal("0.55"),
        predicted_prob=0.62,
        confidence=0.8,
        edge=0.07,
        bankroll=Decimal("10000"),
        current_drawdown=0.05,
        minutes_before_start=30,
    )
    ok, failures = RiskService().validate(intent)
    assert ok
    assert failures == []
