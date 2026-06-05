from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.signals.arbitrage import (
    BinaryMarketQuote,
    SignalCosts,
    find_binary_arbitrage,
    kalshi_taker_fee,
)
from app.signals.dutching import DutchingOutcome, evaluate_dutching
from app.signals.matching import ResolutionTerms, match_resolution_terms


LOCK_TIME = datetime(2026, 1, 15, 0, 30, tzinfo=UTC)


def _terms(
    *,
    platform: str = "polymarket",
    market_id: str = "will-lakers-beat-celtics",
    event_id: str = "nba-lal-bos-2026-01-15",
    entities: tuple[str, ...] = ("los-angeles-lakers", "boston-celtics"),
    close_at: datetime = LOCK_TIME,
    resolution_source: str = "nba-final-score",
) -> ResolutionTerms:
    return ResolutionTerms(
        platform=platform,
        market_id=market_id,
        title="Will the Lakers beat the Celtics?",
        event_id=event_id,
        normalized_entities=entities,
        close_at=close_at,
        resolution_source=resolution_source,
        resolution_rules="YES resolves from the official NBA final score.",
    )


def test_resolution_matching_confirms_same_event_semantics():
    match = match_resolution_terms(
        _terms(),
        _terms(platform="kalshi", market_id="KXNBA-LALBOS-26JAN15"),
    )

    assert match.status == "confirmed"
    assert match.confirmed is True
    assert match.confidence >= 0.9
    assert "event_id_match" in match.reasons
    assert "entity_match" in match.reasons


def test_resolution_matching_rejects_same_title_with_different_entities():
    match = match_resolution_terms(
        _terms(),
        _terms(
            platform="kalshi",
            market_id="KXNBA-GSWBOS-26JAN15",
            event_id="nba-gsw-bos-2026-01-15",
            entities=("golden-state-warriors", "boston-celtics"),
        ),
    )

    assert match.status == "unconfirmed"
    assert match.confirmed is False
    assert match.confidence < 0.75
    assert "event_id_mismatch" in match.reasons
    assert "entity_mismatch" in match.reasons


def test_binary_arbitrage_requires_net_cost_below_one_after_fees():
    match = match_resolution_terms(
        _terms(),
        _terms(platform="kalshi", market_id="KXNBA-LALBOS-26JAN15"),
    )
    signal = find_binary_arbitrage(
        yes_market=BinaryMarketQuote(
            platform="polymarket",
            market_id="poly-lal-bos",
            yes_price=Decimal("0.42"),
            no_price=Decimal("0.58"),
        ),
        no_market=BinaryMarketQuote(
            platform="kalshi",
            market_id="kalshi-lal-bos",
            yes_price=Decimal("0.46"),
            no_price=Decimal("0.54"),
        ),
        resolution_match=match,
        costs=SignalCosts(polymarket_gas_per_contract=Decimal("0.003")),
    )

    assert signal.is_arbitrage is True
    assert signal.headline_eligible is True
    assert signal.gross_cost == Decimal("0.9600")
    assert signal.net_cost == Decimal("0.9830")
    assert signal.net_spread == Decimal("0.0170")
    assert signal.return_pct == pytest.approx(0.017293)
    assert signal.warning == "fee, slippage, liquidity, and resolution-term risk remain"


def test_kalshi_fee_uses_price_dependent_taker_formula():
    assert kalshi_taker_fee(Decimal("0.10")) == Decimal("0.01")
    assert kalshi_taker_fee(Decimal("0.50")) == Decimal("0.02")
    assert kalshi_taker_fee(Decimal("0.90")) == Decimal("0.01")


def test_binary_arbitrage_excludes_boundary_and_unconfirmed_pairs():
    confirmed = match_resolution_terms(
        _terms(),
        _terms(platform="kalshi", market_id="KXNBA-LALBOS-26JAN15"),
    )
    boundary = find_binary_arbitrage(
        yes_market=BinaryMarketQuote(
            platform="polymarket",
            market_id="poly-lal-bos",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.55"),
        ),
        no_market=BinaryMarketQuote(
            platform="kalshi",
            market_id="kalshi-lal-bos",
            yes_price=Decimal("0.47"),
            no_price=Decimal("0.53"),
        ),
        resolution_match=confirmed,
    )

    unconfirmed = find_binary_arbitrage(
        yes_market=boundary.yes_leg.market,
        no_market=boundary.no_leg.market,
        resolution_match=match_resolution_terms(
            _terms(),
            _terms(
                platform="kalshi",
                market_id="KXNBA-GSWBOS-26JAN15",
                event_id="nba-gsw-bos-2026-01-15",
                entities=("golden-state-warriors", "boston-celtics"),
            ),
        ),
    )

    assert boundary.net_cost == Decimal("1.0000")
    assert boundary.is_arbitrage is False
    assert boundary.headline_eligible is False
    assert unconfirmed.is_arbitrage is False
    assert unconfirmed.headline_eligible is False
    assert unconfirmed.resolution_status == "unconfirmed"


def test_dutching_equalizes_payout_when_outcomes_are_exhaustive():
    result = evaluate_dutching(
        [
            DutchingOutcome(name="Lakers", price=Decimal("0.30")),
            DutchingOutcome(name="Celtics", price=Decimal("0.25")),
            DutchingOutcome(name="Draw", price=Decimal("0.20")),
        ],
        exhaustive=True,
        mutually_exclusive=True,
    )

    assert result.risk_free is True
    assert result.coverage_status == "confirmed"
    assert result.total_cost == Decimal("0.7500")
    assert result.guaranteed_payout == Decimal("1.0000")
    assert result.profit == Decimal("0.2500")
    assert result.return_pct == pytest.approx(0.333333)
    assert {leg.outcome: leg.quantity for leg in result.legs} == {
        "Lakers": Decimal("1.0000"),
        "Celtics": Decimal("1.0000"),
        "Draw": Decimal("1.0000"),
    }


def test_dutching_flags_non_exhaustive_coverage_without_risk_free_claim():
    result = evaluate_dutching(
        [
            DutchingOutcome(name="Lakers", price=Decimal("0.30")),
            DutchingOutcome(name="Celtics", price=Decimal("0.25")),
        ],
        exhaustive=False,
        mutually_exclusive=True,
    )

    assert result.coverage_status == "unconfirmed"
    assert result.risk_free is False
    assert result.coverage_warning == "coverage not guaranteed"
