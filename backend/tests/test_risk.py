from decimal import Decimal

import pytest

from app.risk.rules import OrderIntent, RiskService, suggest_fractional_kelly_stake


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


def test_risk_package_exports_kelly_suggestion_api():
    from app.risk import KellyStakeSuggestion, suggest_fractional_kelly_stake

    assert KellyStakeSuggestion
    assert suggest_fractional_kelly_stake


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


def test_risk_rejects_suspended_user():
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
        user_suspended=True,
    )
    ok, failures = RiskService().validate(intent)
    assert not ok
    assert any("suspended" in f for f in failures)


def test_fractional_kelly_suggests_paper_stake_under_hard_cap():
    suggestion = suggest_fractional_kelly_stake(
        predicted_prob=0.62,
        price=Decimal("0.55"),
        bankroll=Decimal("10000"),
    )

    assert suggestion.edge == 0.07
    assert suggestion.kelly_fraction == pytest.approx(0.15555555555555556)
    assert suggestion.fractional_kelly_fraction == pytest.approx(0.03888888888888889)
    assert suggestion.cap_fraction == 0.05
    assert suggestion.stake_notional == Decimal("388.8889")
    assert suggestion.quantity == Decimal("707.0707")
    assert not suggestion.capped
    assert suggestion.paper_trading_only is True


def test_fractional_kelly_caps_large_edges_to_max_bet_pct():
    suggestion = suggest_fractional_kelly_stake(
        predicted_prob=0.95,
        price=Decimal("0.30"),
        bankroll=Decimal("10000"),
    )

    assert suggestion.stake_notional == Decimal("500.0000")
    assert suggestion.quantity == Decimal("1666.6667")
    assert suggestion.capped is True


def test_fractional_kelly_returns_zero_without_positive_edge():
    suggestion = suggest_fractional_kelly_stake(
        predicted_prob=0.50,
        price=Decimal("0.55"),
        bankroll=Decimal("10000"),
    )

    assert suggestion.edge == -0.05
    assert suggestion.stake_notional == Decimal("0.0000")
    assert suggestion.quantity == Decimal("0.0000")


def test_risk_suggests_no_stake_from_yes_probability_and_executable_no_ask():
    intent = OrderIntent(
        market_slug="nba-2025-01-15-lal-bos",
        side="buy",
        outcome="no",
        quantity=Decimal("10"),
        price=Decimal("0.42"),
        predicted_prob=0.30,
        confidence=0.8,
        edge=0.28,
        bankroll=Decimal("10000"),
        current_drawdown=0.0,
        minutes_before_start=30,
    )

    suggestion = RiskService().suggest_stake(intent)

    assert suggestion.predicted_prob == pytest.approx(0.70)
    assert suggestion.price == Decimal("0.4200")
    assert suggestion.edge == 0.28
    assert suggestion.stake_notional == Decimal("500.0000")
    assert suggestion.capped is True


def test_risk_suggests_no_outcome_stake_against_no_executable_ask():
    intent = OrderIntent(
        market_slug="nba-2025-01-15-lal-bos",
        side="buy",
        outcome="no",
        quantity=Decimal("10"),
        price=Decimal("0.62"),
        predicted_prob=0.30,
        confidence=0.8,
        edge=0.08,
        bankroll=Decimal("10000"),
        current_drawdown=0.0,
        minutes_before_start=30,
    )

    suggestion = RiskService().suggest_stake(intent)

    assert suggestion.predicted_prob == pytest.approx(0.70)
    assert suggestion.price == Decimal("0.6200")
    assert suggestion.edge == pytest.approx(0.08)
