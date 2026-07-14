"""Loop V15 C1 — connector HTTP resilience (timeout / jittered retry / circuit breaker).

All tests use httpx.MockTransport — no live network.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from app.data.connectors.http import (
    CircuitOpenError,
    JsonConnectorClient,
    get_source_health,
    reset_source_health,
)


@pytest.fixture(autouse=True)
def _clear_health_registry():
    reset_source_health()
    yield
    reset_source_health()


def _client(
    handler,
    *,
    source: str,
    max_attempts: int = 3,
    failure_threshold: int = 3,
    cooldown_sec: float = 60.0,
    sleeps: list[float] | None = None,
    clock: dict[str, float] | None = None,
) -> JsonConnectorClient:
    clock = clock if clock is not None else {"t": 0.0}
    sleeps = sleeps if sleeps is not None else []

    def sleep(delay: float) -> None:
        sleeps.append(delay)

    def monotonic() -> float:
        return clock["t"]

    return JsonConnectorClient(
        base_url="https://upstream.example.test",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://upstream.example.test",
            timeout=10.0,
        ),
        source=source,
        max_attempts=max_attempts,
        failure_threshold=failure_threshold,
        cooldown_sec=cooldown_sec,
        base_backoff_sec=0.1,
        backoff_cap_sec=1.0,
        sleep=sleep,
        rng=__import__("random").Random(0),
        monotonic=monotonic,
    )


def test_retries_5xx_with_jittered_backoff_then_succeeds():
    calls = {"n": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"err": "busy"})
        return httpx.Response(200, json={"ok": True})

    client = _client(handler, source="retry-demo", sleeps=sleeps)
    assert client.get_json("/v1/data") == {"ok": True}
    assert calls["n"] == 3
    assert len(sleeps) == 2
    assert all(0.0 <= d <= 1.0 for d in sleeps)
    assert client.health().state == "healthy"
    assert client.health().total_successes == 1


def test_timeout_retries_then_opens_circuit_after_threshold(caplog):
    sleeps: list[float] = []
    clock = {"t": 100.0}

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout")

    client = _client(
        handler,
        source="timeout-demo",
        max_attempts=2,
        failure_threshold=2,
        cooldown_sec=30.0,
        sleeps=sleeps,
        clock=clock,
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(httpx.ReadTimeout):
            client.get_json("/slow")
        with pytest.raises(httpx.ReadTimeout):
            client.get_json("/slow")

    health = client.health()
    assert health.consecutive_failures == 2
    assert health.state == "open"
    assert health.open_until == pytest.approx(130.0)
    assert "connector_circuit_opened" in caplog.text

    # While open: skip upstream entirely.
    with pytest.raises(CircuitOpenError) as exc_info:
        client.get_json("/slow")
    assert exc_info.value.source == "timeout-demo"

    # After cooldown: half-open probe allowed; success closes circuit.
    clock["t"] = 130.0
    ok_calls = {"n": 0}

    def ok_handler(request: httpx.Request) -> httpx.Response:
        ok_calls["n"] += 1
        return httpx.Response(200, json={"recovered": True})

    client.client = httpx.Client(
        transport=httpx.MockTransport(ok_handler),
        base_url="https://upstream.example.test",
        timeout=10.0,
    )
    assert client.get_json("/slow") == {"recovered": True}
    assert ok_calls["n"] == 1
    assert client.health().state == "healthy"
    assert client.health().consecutive_failures == 0


def test_per_source_circuit_isolation():
    """A tripped breaker on source A must not block source B."""

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"b": 1})

    a = _client(boom, source="source-a", max_attempts=1, failure_threshold=1, cooldown_sec=60.0)
    b = _client(ok, source="source-b", max_attempts=1, failure_threshold=1, cooldown_sec=60.0)

    with pytest.raises(httpx.ConnectError):
        a.get_json("/a")
    assert a.health().state == "open"
    assert b.get_json("/b") == {"b": 1}
    assert b.health().state == "healthy"
    assert get_source_health("source-a").state == "open"  # type: ignore[union-attr]
    assert get_source_health("source-b").state == "healthy"  # type: ignore[union-attr]


def test_4xx_does_not_trip_circuit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"missing": True})

    client = _client(handler, source="client-err", max_attempts=2, failure_threshold=1)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_json("/missing")
    assert client.health().state == "healthy"
    assert client.health().consecutive_failures == 0


def test_onchain_post_retries_via_shared_client():
    from app.data.connectors.onchain import OnchainReadOnlyConnector

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(502, json={"err": "bad gateway"})
        return httpx.Response(
            200,
            json={
                "data": {
                    "orderFilleds": [
                        {
                            "id": "f1",
                            "transactionHash": "0x1",
                            "timestamp": "2026-01-14T17:00:00Z",
                            "wallet": "0xabc",
                            "market": "m1",
                            "outcome": "YES",
                            "side": "BUY",
                            "price": "0.50",
                            "quantity": "10",
                        }
                    ]
                }
            },
        )

    sleeps: list[float] = []
    http = JsonConnectorClient(
        base_url="",
        client=httpx.Client(transport=httpx.MockTransport(handler), timeout=15.0),
        source="polymarket-subgraph-test",
        max_attempts=3,
        sleep=sleeps.append,
        rng=__import__("random").Random(1),
    )
    connector = OnchainReadOnlyConnector(
        polygon_rpc_url="https://polygon.example.test",
        polymarket_subgraph_url="https://subgraph.example.test/graphql",
        http=http,
    )
    positions = connector.fetch_wallet_positions("0xabc")
    assert calls["n"] == 2
    assert len(sleeps) == 1
    assert len(positions) == 1
    assert positions[0].quantity == __import__("decimal").Decimal("10.0000")
