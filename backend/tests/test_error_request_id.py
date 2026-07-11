"""R03 — structured 5xx logging + request-id header (Loop V13).

A route that raises must:
* return a GENERIC error body (no exception detail / info leak — V11 fix), and
* carry an ``X-Request-ID`` response header for support tracing, and
* cause the 500 handler to log ONE structured record with request-id + method +
  path + exception type (asserted via caplog).

Also asserts the happy path still stamps ``X-Request-ID`` on 200 responses.
"""

from __future__ import annotations

import logging

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.system as system_mod
from app.main import app


@pytest.mark.asyncio
async def test_raising_route_returns_generic_body_and_request_id(monkeypatch, caplog):
    def _boom():
        raise RuntimeError("internal detail that must not leak")

    # /api/v1/system/loops is a public GET with no DB dependency; force its
    # in-process snapshot read to raise so the handler runs.
    monkeypatch.setattr(system_mod, "snapshot", _boom)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="app.main"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/system/loops")

    assert resp.status_code == 500
    # Generic body — the raised message must NOT appear (no info leak).
    body = resp.json()
    assert body == {"detail": "Internal Server Error"}
    assert "internal detail that must not leak" not in resp.text

    # Support-tracing header present and non-empty.
    rid = resp.headers.get("X-Request-ID")
    assert rid, "500 response is missing the X-Request-ID header"

    # Structured log record with the exact context (no traceback in the body).
    records = [r for r in caplog.records if r.message == "Unhandled server error"]
    assert len(records) == 1, f"expected one structured 5xx log, saw {len(records)}"
    rec = records[0]
    assert rec.request_id == rid
    assert rec.method == "GET"
    assert rec.path == "/api/v1/system/loops"
    assert rec.exception_type == "RuntimeError"


@pytest.mark.asyncio
async def test_happy_path_still_carries_request_id():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/system/loops")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_inbound_request_id_is_echoed():
    """A caller-supplied X-Request-ID is preserved end-to-end for tracing."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/system/loops", headers={"X-Request-ID": "trace-abc-123"}
        )
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "trace-abc-123"
