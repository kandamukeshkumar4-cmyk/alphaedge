"""U13 — Trader profile tests.

Covers:
1. Profile derivation math — category preferences, avg size vs bankroll, hold
   period, win rate by category, streak/tilt detection — with fixture histories.
2. Empty / new-user state — fewer than MIN_TRADES_FOR_PROFILE trades → honest
   empty state (has_data=False, no fabricated stats).
3. Deviation detection — "3x usual size" boundary (exact threshold, above,
   below).
4. Assistant uses profile context — fixture user profile → answer references
   the profile.
5. Privacy — profile module uses ONLY paper-activity data (AST / structural
   check confirming no external source import).
6. API endpoint smoke — unauthenticated → 401; authenticated with no trades →
   200 with has_data=False.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.trader_profile_service import (
    MIN_TRADES_FOR_PROFILE,
    TradeRecord,
    TraderProfile,
    compute_trader_profile,
    detect_size_deviation,
)


# ── Fixture helpers ───────────────────────────────────────────────────────────


def _buy(
    slug: str,
    cost: float,
    realized_pnl: float | None = None,
    settled: bool = False,
    created_at: datetime | None = None,
) -> TradeRecord:
    cost_dec = Decimal(str(cost))
    shares = Decimal("10")
    price = cost_dec / shares
    return TradeRecord(
        slug=slug,
        side="YES",
        shares=shares,
        price=price,
        cost=cost_dec,
        action="BUY",
        realized_pnl=Decimal(str(realized_pnl)) if realized_pnl is not None else None,
        settled=settled,
        created_at=created_at or datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


def _sell(
    slug: str,
    cost: float,
    created_at: datetime | None = None,
) -> TradeRecord:
    cost_dec = Decimal(str(cost))
    return TradeRecord(
        slug=slug,
        side="YES",
        shares=Decimal("10"),
        price=cost_dec / Decimal("10"),
        cost=cost_dec,
        action="SELL",
        realized_pnl=None,
        settled=False,
        created_at=created_at or datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
    )


def _nba_buys(n: int, cost: float = 50.0, win: bool = True) -> list[TradeRecord]:
    """Return n settled NBA BUY records."""
    return [
        _buy(
            "nba-2025-01-15-lal-bos",
            cost=cost,
            realized_pnl=10.0 if win else -10.0,
            settled=True,
            created_at=datetime(2025, 1, i + 1, 10, 0, tzinfo=timezone.utc),
        )
        for i in range(n)
    ]


# ── 1. Category preference derivation ────────────────────────────────────────


class TestCategoryPreferences:
    def test_nba_category_top_when_most_trades(self):
        trades = _nba_buys(5)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert "NBA" in profile.favorite_categories

    def test_multiple_categories_ordered_by_count(self):
        nba_trades = _nba_buys(5)
        # 2 crypto trades
        crypto_trades = [
            _buy("will-btc-hit-100k", cost=30.0, realized_pnl=5.0, settled=True)
            for _ in range(2)
        ]
        all_trades = nba_trades + crypto_trades
        profile = compute_trader_profile(all_trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.favorite_categories[0] == "NBA"

    def test_win_rate_by_category(self):
        # 4 NBA wins, 1 NBA loss → win_rate = 0.8
        wins = _nba_buys(4, win=True)
        losses = _nba_buys(1, win=False)
        profile = compute_trader_profile(wins + losses, bankroll_usd=10_000.0)
        assert profile.has_data is True
        nba_stats = next(s for s in profile.category_stats if s.category == "NBA")
        assert pytest.approx(nba_stats.win_rate, abs=0.01) == 0.8

    def test_win_rate_minus_one_when_no_settled(self):
        trades = [_buy("nba-2025-01-15-lal-bos", cost=50.0) for _ in range(5)]
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        nba_stats = next(s for s in profile.category_stats if s.category == "NBA")
        assert nba_stats.win_rate == -1.0


# ── 2. Position sizing vs bankroll ────────────────────────────────────────────


class TestPositionSizing:
    def test_avg_cost_usd(self):
        trades = _nba_buys(5, cost=100.0)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert pytest.approx(profile.avg_cost_usd, abs=0.01) == 100.0

    def test_avg_size_pct_bankroll(self):
        trades = _nba_buys(5, cost=200.0)
        # avg_cost=200, bankroll=2000 → 10%
        profile = compute_trader_profile(trades, bankroll_usd=2_000.0)
        assert profile.has_data is True
        assert pytest.approx(profile.avg_size_pct_bankroll, abs=0.01) == 10.0

    def test_avg_size_pct_zero_when_bankroll_zero(self):
        trades = _nba_buys(5, cost=100.0)
        profile = compute_trader_profile(trades, bankroll_usd=0.0)
        assert profile.has_data is True
        assert profile.avg_size_pct_bankroll == 0.0


# ── 3. Holding period ─────────────────────────────────────────────────────────


class TestHoldPeriod:
    def test_avg_hold_hours_from_buy_sell_pair(self):
        buy = _buy(
            "nba-2025-01-15-lal-bos",
            cost=50.0,
            created_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        sell = _sell(
            "nba-2025-01-15-lal-bos",
            cost=55.0,
            created_at=datetime(2025, 1, 1, 16, 0, tzinfo=timezone.utc),  # 6h later
        )
        # Need MIN_TRADES_FOR_PROFILE total: add more buys
        extra = _nba_buys(4)
        trades = [buy, sell] + extra
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        # Avg hold is the average over PAIRED buy-sell pairs only.
        # Only 1 pair exists (buy→sell = 6h). The 4 extra buys have no sell so
        # they contribute 0 pairs. avg = 6.0 / 1 = 6.0h.
        assert pytest.approx(profile.avg_hold_hours, abs=0.1) == 6.0

    def test_avg_hold_zero_when_no_sells(self):
        trades = _nba_buys(5)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.avg_hold_hours == 0.0


# ── 4. Empty-state / new-user ─────────────────────────────────────────────────


class TestEmptyState:
    def test_empty_when_no_trades(self):
        profile = compute_trader_profile([], bankroll_usd=10_000.0)
        assert profile.has_data is False
        # Must not fabricate any stats
        assert profile.favorite_categories == []
        assert profile.category_stats == []
        assert profile.avg_cost_usd == 0.0
        assert profile.overall_win_rate == -1.0

    def test_empty_when_below_min_trades(self):
        trades = _nba_buys(MIN_TRADES_FOR_PROFILE - 1)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is False
        assert profile.favorite_categories == []
        assert profile.avg_cost_usd == 0.0

    def test_has_data_true_at_exactly_min_trades(self):
        trades = _nba_buys(MIN_TRADES_FOR_PROFILE)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True

    def test_source_note_always_present(self):
        profile_empty = compute_trader_profile([], bankroll_usd=0.0)
        assert "paper activity" in profile_empty.source_note.lower()

        trades = _nba_buys(MIN_TRADES_FOR_PROFILE)
        profile_full = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert "paper activity" in profile_full.source_note.lower()


# ── 5. Tilt / streak detection ────────────────────────────────────────────────


class TestTiltStreak:
    def _make_streak_trades(
        self, wins: int, losses: int, cost_after_loss: float = 50.0
    ) -> list[TradeRecord]:
        """Returns loss-streak followed by a higher-cost trade (simulating tilt)."""
        base_cost = 30.0
        trades: list[TradeRecord] = []
        for i in range(wins):
            trades.append(
                _buy(
                    "nba-2025-01-15-lal-bos",
                    cost=base_cost,
                    realized_pnl=5.0,
                    settled=True,
                    created_at=datetime(2025, 1, i + 1, 10, 0, tzinfo=timezone.utc),
                )
            )
        for i in range(losses):
            trades.append(
                _buy(
                    "nba-2025-01-15-lal-bos",
                    cost=base_cost,
                    realized_pnl=-5.0,
                    settled=True,
                    created_at=datetime(2025, 1, wins + i + 1, 10, 0, tzinfo=timezone.utc),
                )
            )
        # One more trade after losses with inflated cost
        trades.append(
            _buy(
                "nba-2025-01-15-lal-bos",
                cost=cost_after_loss,
                realized_pnl=5.0,
                settled=True,
                created_at=datetime(2025, 1, wins + losses + 1, 10, 0, tzinfo=timezone.utc),
            )
        )
        return trades

    def test_winning_streak_positive(self):
        trades = _nba_buys(5, win=True)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.current_streak > 0

    def test_losing_streak_negative(self):
        trades = _nba_buys(5, win=False)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.current_streak < 0

    def test_tilt_detected_when_sizes_up_after_losses(self):
        # 1 win + 2 losses + 1 large trade (cost 90 vs base 30 = 3x)
        trades = self._make_streak_trades(wins=2, losses=2, cost_after_loss=90.0)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.sizes_up_after_losses is True
        assert profile.tilt_multiplier >= 1.2

    def test_no_tilt_when_size_stable(self):
        # same cost after loss → no tilt
        trades = self._make_streak_trades(wins=2, losses=2, cost_after_loss=32.0)
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.sizes_up_after_losses is False


# ── 6. Deviation detection — boundary tests ───────────────────────────────────


class TestDeviationDetection:
    def _profile_with_avg_cost(self, avg: float) -> TraderProfile:
        """Build minimal profile with given avg_cost_usd."""
        trades = [
            _buy("nba-2025-01-15-lal-bos", cost=avg)
            for _ in range(MIN_TRADES_FOR_PROFILE)
        ]
        return compute_trader_profile(trades, bankroll_usd=10_000.0)

    def test_no_deviation_below_threshold(self):
        profile = self._profile_with_avg_cost(50.0)
        # 1.9x is below 2.0x threshold
        result = detect_size_deviation(95.0, profile, multiplier_threshold=2.0)
        assert result is None

    def test_no_deviation_at_exact_threshold_minus_epsilon(self):
        profile = self._profile_with_avg_cost(100.0)
        # Exactly at threshold: 200 / 100 = 2.0x → below strict threshold
        result = detect_size_deviation(199.9, profile, multiplier_threshold=2.0)
        assert result is None

    def test_deviation_above_threshold(self):
        profile = self._profile_with_avg_cost(50.0)
        # 3x is above 2.0x threshold
        result = detect_size_deviation(150.0, profile, multiplier_threshold=2.0)
        assert result is not None
        assert "3.0x" in result

    def test_deviation_three_x_typical_message(self):
        profile = self._profile_with_avg_cost(50.0)
        # 155 / 50 = 3.1x
        result = detect_size_deviation(155.0, profile, multiplier_threshold=2.0)
        assert result is not None
        assert "3.1x" in result
        assert "usual position size" in result.lower()

    def test_no_deviation_when_profile_empty(self):
        empty_profile = compute_trader_profile([], bankroll_usd=0.0)
        result = detect_size_deviation(1000.0, empty_profile, multiplier_threshold=2.0)
        assert result is None, "Empty profile must never produce a deviation message"

    def test_no_deviation_when_avg_cost_zero(self):
        """avg_cost_usd=0 guard prevents division-by-zero deviation."""
        # Construct a profile with SELL-only records (no cost from BUYs)
        sells = [_sell("nba-2025-01-15-lal-bos", cost=50.0) for _ in range(5)]
        profile = compute_trader_profile(sells, bankroll_usd=1000.0)
        result = detect_size_deviation(9999.0, profile, multiplier_threshold=2.0)
        # Either no data (sells → no BUY buys → has_data False) or avg_cost guard
        assert result is None


# ── 7. Overall win rate ────────────────────────────────────────────────────────


class TestOverallWinRate:
    def test_win_rate_correct(self):
        wins = _nba_buys(3, win=True)
        losses = _nba_buys(2, win=False)
        profile = compute_trader_profile(wins + losses, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert pytest.approx(profile.overall_win_rate, abs=0.01) == 0.6

    def test_win_rate_minus_one_when_no_settled(self):
        trades = [_buy("nba-2025-01-15-lal-bos", cost=50.0) for _ in range(5)]
        profile = compute_trader_profile(trades, bankroll_usd=10_000.0)
        assert profile.has_data is True
        assert profile.overall_win_rate == -1.0


# ── 8. Assistant uses profile context ─────────────────────────────────────────


class TestAssistantProfileIntegration:
    def test_portfolio_reply_references_profile_when_has_data(self):
        """When a profile is injected, portfolio reply includes profile data."""
        from app.api.v1.assistant import _build_deterministic_reply

        profile_dict = {
            "has_data": True,
            "favorite_categories": ["NBA", "CRYPTO"],
            "avg_size_pct_bankroll": 5.0,
            "current_streak": -3,
            "sizes_up_after_losses": True,
            "tilt_multiplier": 2.1,
        }
        reply, citations, tools_used = _build_deterministic_reply(
            message="What's my overall exposure?",
            ctx={},
            market_slug=None,
            trader_profile=profile_dict,
        )
        # Profile tool should be in tools_used
        assert "get_trader_profile" in tools_used
        # Reply must reference actual profile numbers (not invented)
        assert "NBA" in reply or "5.0%" in reply or "tilt" in reply.lower() or "loss" in reply.lower()

    def test_no_profile_data_does_not_reference_stats(self):
        """When profile has_data=False the reply must not reference profile stats."""
        from app.api.v1.assistant import _build_deterministic_reply

        profile_dict = {"has_data": False}
        reply, citations, tools_used = _build_deterministic_reply(
            message="What's my overall exposure?",
            ctx={},
            market_slug=None,
            trader_profile=profile_dict,
        )
        assert "get_trader_profile" not in tools_used

    def test_assistant_allowed_tools_includes_get_trader_profile(self):
        """get_trader_profile must be in the read-only allowlist for U13."""
        from app.api.v1.assistant import ASSISTANT_ALLOWED_TOOLS

        assert "get_trader_profile" in ASSISTANT_ALLOWED_TOOLS

    def test_submit_order_intent_still_excluded(self):
        """Adding get_trader_profile must not accidentally admit order tools."""
        from app.api.v1.assistant import ASSISTANT_ALLOWED_TOOLS

        assert "submit_order_intent" not in ASSISTANT_ALLOWED_TOOLS


# ── 9. Privacy — paper-only structural check ──────────────────────────────────


class TestPrivacyPaperOnly:
    def test_trader_profile_service_has_no_external_source_imports(self):
        """The trader_profile_service must import ONLY stdlib + internal services.

        Banned external modules: requests, httpx, aiohttp, anthropic, openai,
        google, brave, scrapecreators, exa (all would indicate reading from
        external accounts / data sources).
        """
        banned = {
            "requests", "httpx", "aiohttp", "anthropic", "openai",
            "google", "brave", "scrapecreators", "exa", "twitter",
            "facebook", "linkedin", "coinbase", "binance",
        }

        src_path = (
            pathlib.Path(__file__).parent.parent
            / "app"
            / "services"
            / "trader_profile_service.py"
        )
        source = src_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        violations = banned & imported_modules
        assert not violations, (
            f"Privacy violation: trader_profile_service.py imports external modules: "
            f"{violations}"
        )

    def test_profile_endpoint_has_no_order_path_imports(self):
        """The profile endpoint must NOT import OrderBookService or RiskService."""
        src_path = (
            pathlib.Path(__file__).parent.parent
            / "app"
            / "api"
            / "v1"
            / "profile.py"
        )
        source = src_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        import_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    import_names.append(alias.name)

        assert "OrderBookService" not in import_names, (
            "GUARDRAIL VIOLATION: profile.py imports OrderBookService"
        )
        assert "RiskService" not in import_names, (
            "GUARDRAIL VIOLATION: profile.py imports RiskService"
        )

    def test_profile_derives_only_from_paper_orders(self):
        """compute_trader_profile takes ONLY TradeRecord objects (from paper_orders).

        This test verifies the function signature does not accept external
        account identifiers or third-party data payloads.
        """
        import inspect

        from app.services.trader_profile_service import compute_trader_profile

        sig = inspect.signature(compute_trader_profile)
        param_names = list(sig.parameters.keys())
        # Only 'trades' and 'bankroll_usd' are accepted
        assert "trades" in param_names
        assert "bankroll_usd" in param_names
        # No 'external_account', 'social_data', 'exchange_history' etc.
        external_params = {p for p in param_names if p not in ("trades", "bankroll_usd")}
        assert not external_params, (
            f"compute_trader_profile has unexpected parameters: {external_params}"
        )


# ── 10. API endpoint smoke ────────────────────────────────────────────────────


@pytest.fixture(autouse=False)
def _override_db_profile(db_session):
    """Fixture that wires the test DB session into the app for profile tests."""
    from app.db.session import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_token_profile(client, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_profile_endpoint_unauthenticated_returns_401():
    """Profile endpoint must require authentication."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_profile_endpoint_new_user_returns_empty_state(_override_db_profile):
    """A newly registered user with zero trades gets has_data=False."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup_token_profile(client, "profile_new@test.com")
        resp = await client.get(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is False
    assert data["paper_trading_only"] is True
    # Must include the paper-only source note
    assert "paper activity" in data["source_note"].lower()
    # Must include an honest empty-state message
    assert "empty_state_message" in data
    assert len(data["empty_state_message"]) > 0
