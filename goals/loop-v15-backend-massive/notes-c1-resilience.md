# C1 — Connector resilience audit

## Exists (before)

- `JsonConnectorClient`: 10s timeout, 5xx retry (max 3), response cache
- Fred: per-series try/except isolation
- Onchain: 15s timeout only (no retry / breaker)

## Added

- Named `source` on `JsonConnectorClient` (odds/fred/worldbank/onchain/kalshi/polymarket)
- Full-jitter exponential backoff between retries (injectable sleep/rng)
- Per-source circuit breaker: after M consecutive transport/5xx failures, skip for N minutes (`CircuitOpenError`)
- 4xx does not trip the breaker
- Structured warning logs on degrade / circuit open / retry
- Module `get_source_health()` registry for C3
- Onchain POSTs go through the same resilient `post_json` path

## Tests

`backend/tests/test_http_connector_resilience.py` — MockTransport only, no live network.
