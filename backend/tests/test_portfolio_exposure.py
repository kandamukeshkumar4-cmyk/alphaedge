"""Tests for U04 portfolio exposure analysis.

Covers:
- derive_underlier_key: NBA, FIFA WC2026, crypto, election, category fallback,
  unknown slug
- compute_exposure: aggregation math, net directional sign, concentration
  threshold boundary (just below / just above 40 %), empty portfolio,
  single-position (concentration at 100 % > 40 %)
- Endpoint smoke: GET /api/v1/portfolio/exposure unauthenticated → 401;
  authenticated empty book → 200 zero state.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.exposure_service import (
    PositionInput,
    compute_exposure,
    derive_underlier_key,
)


# ── derive_underlier_key ──────────────────────────────────────────────────────


class TestDeriveUnderlierKey:
    def test_nba_slug_extracts_first_team(self):
        assert derive_underlier_key("nba-2025-01-15-lal-bos") == "NBA:LAL"

    def test_nba_slug_second_example(self):
        assert derive_underlier_key("nba-2025-02-20-gsw-den") == "NBA:GSW"

    def test_nba_category_match_no_team_in_slug(self):
        assert derive_underlier_key("random-market-slug", category="NBA") == "NBA:OTHER"

    def test_fifa_wc2026_group(self):
        assert derive_underlier_key("fifa-wc2026-group-a-usa-uk") == "FIFA_WC2026:GROUP_A"

    def test_fifa_wc2026_no_group(self):
        assert derive_underlier_key("fifa-wc2026-final") == "FIFA_WC2026:OTHER"

    def test_crypto_btc(self):
        assert derive_underlier_key("will-btc-hit-100k") == "CRYPTO:BTC"

    def test_crypto_eth(self):
        assert derive_underlier_key("eth-price-above-5k-2025") == "CRYPTO:ETH"

    def test_crypto_sol(self):
        assert derive_underlier_key("sol-reaches-200-by-eoy") == "CRYPTO:SOL"

    def test_election_slug(self):
        assert derive_underlier_key("us-president-election-2024") == "ELECTIONS"

    def test_election_category(self):
        assert derive_underlier_key("some-unknown-slug", category="US Elections") == "ELECTIONS"

    def test_category_fallback(self):
        assert derive_underlier_key("some-random-slug", category="Weather") == "WEATHER"

    def test_unknown_slug_returns_other(self):
        assert derive_underlier_key("xyz-abc-def-123") == "OTHER"


# ── compute_exposure ──────────────────────────────────────────────────────────


class TestComputeExposure:
    def test_empty_portfolio(self):
        summary = compute_exposure([])
        assert summary.total_open_notional == 0.0
        assert summary.groups == []
        assert summary.has_concentration is False
        assert summary.concentrated_underliers == []

    def test_single_position_concentration_at_100_pct(self):
        """A single position is 100 % of total, which is > 40 % threshold."""
        pos = PositionInput(
            market_slug="nba-2025-01-15-lal-bos",
            outcome="yes",
            shares=10.0,
            avg_cost=0.60,
        )
        summary = compute_exposure([pos])
        assert len(summary.groups) == 1
        g = summary.groups[0]
        assert g.underlier == "NBA:LAL"
        assert g.pct_of_total == pytest.approx(100.0)
        assert g.concentrated is True
        assert summary.has_concentration is True

    def test_net_directional_yes_positive(self):
        pos = PositionInput(
            market_slug="nba-2025-01-15-lal-bos",
            outcome="yes",
            shares=10.0,
            avg_cost=0.60,
        )
        summary = compute_exposure([pos])
        assert summary.groups[0].net_directional == pytest.approx(6.0)

    def test_net_directional_no_negative(self):
        pos = PositionInput(
            market_slug="nba-2025-01-15-lal-bos",
            outcome="no",
            shares=10.0,
            avg_cost=0.40,
        )
        summary = compute_exposure([pos])
        assert summary.groups[0].net_directional == pytest.approx(-4.0)

    def test_two_positions_same_underlier_aggregated(self):
        """Two markets on the same team aggregate into one group."""
        pos1 = PositionInput(
            market_slug="nba-2025-01-15-lal-bos",
            outcome="yes",
            shares=10.0,
            avg_cost=0.60,
        )
        pos2 = PositionInput(
            market_slug="nba-2025-01-20-lal-gsw",
            outcome="yes",
            shares=5.0,
            avg_cost=0.70,
        )
        summary = compute_exposure([pos1, pos2])
        assert len(summary.groups) == 1
        g = summary.groups[0]
        assert g.underlier == "NBA:LAL"
        assert g.position_count == 2
        assert g.total_notional == pytest.approx(6.0 + 3.5)

    def test_concentration_threshold_just_below_40(self):
        """Three roughly equal groups (~33 % each): no concentration."""
        positions = [
            PositionInput(market_slug="nba-2025-01-15-lal-bos", outcome="yes", shares=33.0, avg_cost=1.0),
            PositionInput(market_slug="will-btc-hit-100k", outcome="yes", shares=33.0, avg_cost=1.0),
            PositionInput(market_slug="us-president-election-2024", outcome="yes", shares=34.0, avg_cost=1.0),
        ]
        summary = compute_exposure(positions)
        for g in summary.groups:
            assert g.concentrated is False
        assert summary.has_concentration is False

    def test_concentration_threshold_just_above_40(self):
        """41 % in one underlier → concentrated flag."""
        pos_big = PositionInput(
            market_slug="nba-2025-01-15-lal-bos",
            outcome="yes",
            shares=41.0,
            avg_cost=1.0,
        )
        pos_small = PositionInput(
            market_slug="will-btc-hit-100k",
            outcome="yes",
            shares=59.0,
            avg_cost=1.0,
        )
        summary = compute_exposure([pos_big, pos_small])
        lal_group = next(g for g in summary.groups if g.underlier == "NBA:LAL")
        assert lal_group.concentrated is True
        assert summary.has_concentration is True

    def test_concentration_exactly_at_threshold_not_concentrated(self):
        """Exactly 40 % is NOT concentrated (strictly >)."""
        pos_big = PositionInput(
            market_slug="nba-2025-01-15-lal-bos",
            outcome="yes",
            shares=40.0,
            avg_cost=1.0,
        )
        pos_small = PositionInput(
            market_slug="will-btc-hit-100k",
            outcome="yes",
            shares=60.0,
            avg_cost=1.0,
        )
        summary = compute_exposure([pos_big, pos_small])
        lal_group = next(g for g in summary.groups if g.underlier == "NBA:LAL")
        assert lal_group.pct_of_total == pytest.approx(40.0)
        assert lal_group.concentrated is False

    def test_groups_sorted_by_notional_descending(self):
        positions = [
            PositionInput(market_slug="will-btc-hit-100k", outcome="yes", shares=1.0, avg_cost=0.10),
            PositionInput(market_slug="nba-2025-01-15-lal-bos", outcome="yes", shares=10.0, avg_cost=0.60),
        ]
        summary = compute_exposure(positions)
        assert summary.groups[0].total_notional >= summary.groups[1].total_notional

    def test_total_notional_correct(self):
        positions = [
            PositionInput(market_slug="nba-2025-01-15-lal-bos", outcome="yes", shares=10.0, avg_cost=0.60),
            PositionInput(market_slug="will-btc-hit-100k", outcome="yes", shares=5.0, avg_cost=0.40),
        ]
        summary = compute_exposure(positions)
        assert summary.total_open_notional == pytest.approx(6.0 + 2.0)

    def test_paper_trading_only_flag(self):
        summary = compute_exposure([])
        assert summary.paper_trading_only is True


# ── endpoint smoke tests ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_exposure_endpoint_unauthenticated():
    """Unauthenticated request must return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/exposure")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_exposure_endpoint_empty_portfolio(db_session):
    """Authenticated user with no trades returns zero-state response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Sign up
        r = await client.post(
            "/api/v1/auth/signup",
            json={"email": "exposure-empty@example.com", "password": "securepass1"},
        )
        assert r.status_code == 201
        token = r.json()["access_token"]

        resp = await client.get(
            "/api/v1/portfolio/exposure",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_open_notional"] == 0.0
    assert body["groups"] == []
    assert body["has_concentration"] is False
    assert body["paper_trading_only"] is True
    assert "paper trading" in body["disclaimer"].lower()
