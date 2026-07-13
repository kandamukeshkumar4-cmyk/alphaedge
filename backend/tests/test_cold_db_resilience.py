"""REL-COLD-DB — graceful behavior when the managed Postgres endpoint is cold.

On Neon scale-to-zero the first request after idle can hit a DB that is still
resuming. Two guarantees pinned here:

1. A DB-connectivity error (OperationalError/InterfaceError) surfaces as HTTP
   503 + Retry-After, NOT a raw 500 — so the frontend degrades to its Demo/
   loading state instead of showing a broken page. A ProgrammingError (real
   bug) must still be a 500 (a cold DB must not mask bugs).
2. `warmup_db` retries a cold endpoint at startup and gives up gracefully
   (returns False, no crash) instead of blocking boot forever.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import InterfaceError, OperationalError, ProgrammingError

from app.main import db_unavailable_handler, unhandled_exception_handler


def _app_with_handlers() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(OperationalError, db_unavailable_handler)
    app.add_exception_handler(InterfaceError, db_unavailable_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/boom-operational")
    async def boom_operational():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    @app.get("/boom-interface")
    async def boom_interface():
        raise InterfaceError("SELECT 1", {}, Exception("connection reset"))

    @app.get("/boom-programming")
    async def boom_programming():
        raise ProgrammingError("SELECT bad", {}, Exception("syntax error"))

    return app


@pytest.fixture
def client() -> TestClient:
    # raise_server_exceptions=False so the handler runs instead of re-raising.
    return TestClient(_app_with_handlers(), raise_server_exceptions=False)


def test_operational_error_becomes_503_with_retry_after(client: TestClient):
    resp = client.get("/boom-operational")
    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "3"
    assert "unavailable" in resp.json()["detail"].lower()


def test_interface_error_becomes_503(client: TestClient):
    resp = client.get("/boom-interface")
    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "3"


def test_programming_error_still_500(client: TestClient):
    """A cold DB must not mask a real SQL bug — non-connectivity errors stay 500."""
    resp = client.get("/boom-programming")
    assert resp.status_code == 500


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *_a, **_k):
        return None


class _FakeEngine:
    """Stands in for the AsyncEngine (whose `connect` attr is read-only, so it
    can't be monkeypatched in place). `fail_first` connect attempts raise a
    cold-start OperationalError, the rest succeed."""

    def __init__(self, fail_first: int):
        self.fail_first = fail_first
        self.calls = 0

    def connect(self):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise OperationalError("SELECT 1", {}, Exception("cold"))
        return _FakeConn()


@pytest.mark.asyncio
async def test_warmup_db_succeeds_after_transient_failures(monkeypatch):
    from app.db import session as session_mod

    fake = _FakeEngine(fail_first=2)
    monkeypatch.setattr(session_mod, "engine", fake)
    monkeypatch.setattr(session_mod.asyncio, "sleep", _noop_sleep)

    ok = await session_mod.warmup_db(retries=5, delay_sec=0.01)
    assert ok is True
    assert fake.calls == 3  # failed twice, succeeded on the third


@pytest.mark.asyncio
async def test_warmup_db_gives_up_gracefully(monkeypatch):
    from app.db import session as session_mod

    fake = _FakeEngine(fail_first=99)  # never recovers
    monkeypatch.setattr(session_mod, "engine", fake)
    monkeypatch.setattr(session_mod.asyncio, "sleep", _noop_sleep)

    ok = await session_mod.warmup_db(retries=3, delay_sec=0.01)
    assert ok is False  # exhausted, no crash
    assert fake.calls == 3  # tried exactly `retries` times


async def _noop_sleep(_sec: float) -> None:
    # A real no-op: patching asyncio.sleep globally means calling asyncio.sleep
    # here would recurse into this function.
    return None
