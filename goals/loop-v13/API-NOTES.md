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
