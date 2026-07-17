"""Loop V59 H5 — order-path guard + loop registration for heartbeat manager."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from app.observability.loop_state import LOOP_INTERVALS


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "app" / "services" / "heartbeat_manager.py"
DECISION = ROOT / "app" / "services" / "heartbeat_decision.py"
HALTS = ROOT / "app" / "services" / "heartbeat_halts.py"


def test_decision_engine_has_no_order_imports():
    src = DECISION.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "order_book" not in alias.name
                assert alias.name != "app.db.models"
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "order_book" not in mod
            assert mod != "app.risk.rules"


def test_halts_module_has_no_order_path():
    src = HALTS.read_text(encoding="utf-8")
    assert "OrderBookService" not in src
    assert "submit_order" not in src
    assert "RiskService" not in src


def test_manager_exits_only_via_risk_then_orderbook():
    src = MANAGER.read_text(encoding="utf-8")
    assert "RiskService" in src
    assert "OrderIntent" in src
    assert "OrderBookService" in src
    assert "is_exit=True" in src
    # No raw Order(...) construction for bypass inserts.
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Order":
                pytest.fail("heartbeat_manager must not construct Order directly")
            if isinstance(func, ast.Attribute) and func.attr == "add":
                # session.add(Order(...)) would still be caught by Order() above
                pass


def test_loop_interval_and_all_loops_registration():
    from app.api.v1.system import _ALL_LOOPS

    assert "heartbeat_manager" in _ALL_LOOPS
    assert LOOP_INTERVALS["heartbeat_manager"] == 45


@pytest.mark.asyncio
async def test_lifespan_registers_heartbeat_when_enabled(monkeypatch):
    import app.main as main_mod
    from app.main import lifespan

    class _FakeSession:
        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

    def _fake_session_local():
        class _Ctx:
            async def __aenter__(self):
                return _FakeSession()

            async def __aexit__(self, *exc):
                return False

        return _Ctx()

    class _FakeMarketService:
        def __init__(self, session):
            pass

        async def seed_system_account(self, *args, **kwargs):
            return None

        async def seed_catalog_markets(self):
            return None

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(main_mod, "AsyncSessionLocal", _fake_session_local)
    monkeypatch.setattr(main_mod, "MarketService", _FakeMarketService)
    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.services.signal_event_seed.seed_signal_events", _noop)
    monkeypatch.setattr("app.data.streams.runner.background_loop_plan", lambda s: [])
    monkeypatch.setattr(main_mod.settings, "live_feed_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_news_scan_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_news_mispricing_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_unusual_flow_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_weather_scan_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_morning_research_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_whale_refresh_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_wc2026_resolve_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_external_resolve_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_external_market_bridge_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_external_autolock_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_drift_detect_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_ops_alerts_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_portfolio_equity_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_daily_digest_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_jobrun_retention_enabled", False)
    monkeypatch.setattr(main_mod.settings, "scheduler_data_retention_enabled", False)
    monkeypatch.setattr(main_mod.settings, "heartbeat_manager_enabled", True)

    created: list[str] = []
    tasks: list[asyncio.Task] = []
    real = asyncio.create_task

    def spy(coro, *args, **kwargs):
        code = getattr(coro, "cr_code", None)
        if code is not None:
            created.append(code.co_name)
        task = real(coro, *args, **kwargs)
        tasks.append(task)
        return task

    monkeypatch.setattr(main_mod.asyncio, "create_task", spy)

    class _App:
        pass

    try:
        async with lifespan(_App()):
            assert "_heartbeat_manager_loop" in created
            assert "_price_feed_loop" in created
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_lifespan_skips_heartbeat_when_disabled(monkeypatch):
    import app.main as main_mod
    from app.main import lifespan

    class _FakeSession:
        async def commit(self) -> None:
            return None

    def _fake_session_local():
        class _Ctx:
            async def __aenter__(self):
                return _FakeSession()

            async def __aexit__(self, *exc):
                return False

        return _Ctx()

    class _FakeMarketService:
        def __init__(self, session):
            pass

        async def seed_system_account(self, *args, **kwargs):
            return None

        async def seed_catalog_markets(self):
            return None

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(main_mod, "AsyncSessionLocal", _fake_session_local)
    monkeypatch.setattr(main_mod, "MarketService", _FakeMarketService)
    monkeypatch.setattr("app.db.session.warmup_db", _noop)
    monkeypatch.setattr("app.services.signal_event_seed.seed_signal_events", _noop)
    monkeypatch.setattr("app.data.streams.runner.background_loop_plan", lambda s: [])
    monkeypatch.setattr(main_mod.settings, "live_feed_enabled", False)
    for attr in (
        "scheduler_news_scan_enabled",
        "scheduler_news_mispricing_enabled",
        "scheduler_unusual_flow_enabled",
        "scheduler_weather_scan_enabled",
        "scheduler_morning_research_enabled",
        "scheduler_whale_refresh_enabled",
        "scheduler_wc2026_resolve_enabled",
        "scheduler_external_resolve_enabled",
        "scheduler_external_market_bridge_enabled",
        "scheduler_external_autolock_enabled",
        "scheduler_drift_detect_enabled",
        "scheduler_ops_alerts_enabled",
        "scheduler_portfolio_equity_enabled",
        "scheduler_daily_digest_enabled",
        "scheduler_jobrun_retention_enabled",
        "scheduler_data_retention_enabled",
    ):
        monkeypatch.setattr(main_mod.settings, attr, False)
    monkeypatch.setattr(main_mod.settings, "heartbeat_manager_enabled", False)

    created: list[str] = []
    tasks: list[asyncio.Task] = []
    real = asyncio.create_task

    def spy(coro, *args, **kwargs):
        code = getattr(coro, "cr_code", None)
        if code is not None:
            created.append(code.co_name)
        task = real(coro, *args, **kwargs)
        tasks.append(task)
        return task

    monkeypatch.setattr(main_mod.asyncio, "create_task", spy)

    class _App:
        pass

    try:
        async with lifespan(_App()):
            assert "_heartbeat_manager_loop" not in created
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
