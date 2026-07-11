# Loop V13 — Backend API notes (observability & resilience)

Additive only. No contract change to existing routes; every existing endpoint
test passes unchanged.

## R01 — `GET /api/v1/system/metrics` (PUBLIC GET, read-only)

Real in-process counters only — never fabricated. Recorded by a lightweight
timing middleware (`app.core.middleware.HttpMetricsMiddleware` →
`app.observability.http_metrics`) and cheap hit/miss counters added to the
desk / opportunities / snapshot micro-caches.

Response JSON:

```json
{
  "uptime_seconds": 12.345,
  "routes": [
    {
      "method": "GET",
      "route": "/api/v1/system/loops",
      "request_count": 3,
      "error_count": 0,
      "p50_latency_ms": 4.1,
      "p95_latency_ms": 9.7
    }
  ],
  "caches": {
    "desk":          {"hits": 0, "misses": 0},
    "opportunities": {"hits": 0, "misses": 0},
    "snapshot":      {"hits": 0, "misses": 0}
  },
  "paper_trading_only": true
}
```

Field notes:

- `uptime_seconds` — wall-clock seconds since the process booted.
- `routes[]` — one row per matched `(method, templated-path)`. Path params are
  collapsed to the route template (e.g. `/api/v1/markets/{slug}`), so the key
  space is bounded by the number of registered routes; a hard `_MAX_ROUTES=512`
  cap is a second guard. `error_count` counts **5xx only** (client 4xx are not
  errors). Latency percentiles are nearest-rank over a bounded per-route ring
  (`_LATENCY_RING=512`).
- `caches` — hit/miss counters for the three in-process micro-caches. A
  TTL-expired entry counts as a miss (matches the caller rebuilding).
- **Honest zeros**: before any traffic, `routes` is `[]` and every cache stat is
  `{hits:0, misses:0}`. Nothing is ever invented.

No DB write, no order path import, no new dependency. Swept by the I01
public-GET 5xx guard (added to `MUST_COVER`).

## R02 — External-connector resilience audit

No response-shape change. Audit of every request-time external touchpoint plus
the Neon session; gaps hardened so a slow/failing external can never turn a
PUBLIC GET into a 5xx.

Audit findings (as-is → action):

| Connector / path | Timeout | Bounded retry | Graceful degrade | Action |
|---|---|---|---|---|
| `JsonConnectorClient` (FRED, World Bank, Kalshi REST, Polymarket gamma/clob, odds) | 10s default | yes (`max_attempts=3`, 5xx-only) | raises to caller | already hardened — no change |
| `NWSForecastConnector` (weather) | 10s explicit | via `JsonConnectorClient` | per-city `try` in `scan` | already hardened |
| `FredConnector.fetch_indicators` | (client) | (client) | per-series `try` → `[]` | already hardened |
| `OnchainReadOnlyConnector` | 15s (fallback client) | none (single POST) | raises to caller (leaderboard/ingest, not request-time GET) | already bounded |
| **`GET /api/v1/macro` route** | — | — | **relied on connector guards** | **added top-level `try` → honest-empty `MacroOut(source="none")`, failure not cached** |
| **`GET /api/v1/weather/edges` route** | — | — | **relied on `scan` per-city guards** | **added top-level `try` → honest-empty `cities=[]`, failure NOT cached (retries next call)** |
| **Neon async engine (`db/session.py`)** | **none** | pool_pre_ping | request errors → 500 (inherent) | **added asyncpg `connect_args={"timeout": 15.0}` so a hung Neon cold-start fails fast instead of blocking indefinitely** |

Hardened (exact list): `app/api/v1/macro.py::macro_dashboard`,
`app/api/v1/weather.py::weather_edges`,
`app/db/session.py::async_engine_settings` (asyncpg connect timeout).

Test: `tests/test_connector_resilience.py` monkeypatches `FredConnector.fetch_indicators`
(→ `httpx.TimeoutException`) and `WeatherDeskService.scan` (→ `httpx.ConnectError`)
and asserts the dependent public GET returns `<500` with an honest-empty body,
plus that a weather failure is not cached.

## R03 — Structured error logging + request-id

Every request carries a request-id (`RequestIdMiddleware`, pre-existing): an
inbound `X-Request-ID` header is echoed, otherwise a uuid4 is generated, and the
value is stamped on the response `X-Request-ID` header.

New: a global `Exception` handler (`app/main.py::unhandled_exception_handler`)
closes two gaps for 5xx responses:

- **Structured log** — one `logging.ERROR` record ("Unhandled server error") with
  `extra={request_id, method, path, exception_type}` and `exc_info=True` for the
  server-side traceback. No secrets/PII; the exception MESSAGE never reaches the
  client.
- **Generic body + request-id header** — returns `{"detail": "Internal Server
  Error"}` (V11 info-leak fix preserved) and re-attaches the `X-Request-ID`
  header, which the request-id middleware's own header write would otherwise skip
  when the downstream app raises before producing a response. Support can now
  correlate a user-reported request-id with the exact server log line.

Test: `tests/test_error_request_id.py` — a monkeypatched raising route returns the
generic body (raised message absent), an `X-Request-ID` header, and exactly one
structured log record with the matching request-id / method / path / exception
type (asserted via caplog); the happy path still stamps `X-Request-ID`; an
inbound request-id is echoed end-to-end.
