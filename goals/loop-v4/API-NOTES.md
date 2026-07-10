# Loop V4 — Backend API notes

Frontend track integrates from this file. **Additive only** — never change or
remove an existing response shape. All surfaces here are ANALYSIS ONLY
(`signal_only` / `paper_trading_only` true); no order path.

## I01 — Public-GET 5xx guard (2026-07-10)

No new HTTP route. A standing local test
(`backend/tests/test_public_get_5xx_guard.py`) that seeds the prod data shape
which crashed `/api/v1/calibration/latest` (RESOLVED market with
`winning_outcome` + a paper order + populated `resolved_at`), plus an open
market with zero candles and otherwise-empty tables, then sweeps EVERY public
GET route in `app.openapi()` and fails on any 5xx. Auth/admin routes and
non-slug path params are skipped honestly; `{slug}` path params and required
`slug` query params are swept with both seeded slugs. Request-time upstream
connectors (FRED macro, NWS weather) are stubbed to their honest-empty
failure results so the sweep is offline. The sweep hard-asserts it still
covers `/api/v1/calibration/latest`, `/api/v1/track-record`, and
`/api/v1/backtest/summary`, so the guard cannot be silently narrowed.
