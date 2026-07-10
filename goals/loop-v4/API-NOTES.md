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

## I02 — `GET /api/v1/system/resolved-count` (2026-07-10)

Public, read-only readout of the G06 resolved-count watcher so the
LightGBM-vs-XGBoost A/B unblock status is visible without admin access. Same
count definition as track-record's `n` (scored LIVE forecasts on RESOLVED
external markets, falling back to resolved paper-order markets). The A/B
harness NEVER flips the deployed default model; `model_default` reports
whatever `ML_MODEL_TYPE` says. No params.

| field | type | notes |
|-------|------|-------|
| `resolved_count` | int | real resolved outcomes; 0 on an empty DB (honest) |
| `ab_threshold` | int | 100 (`MIN_RESOLVED_FOR_AB`) |
| `ab_ready` | bool | `resolved_count >= ab_threshold` |
| `model_default` | string | deployed default model type (e.g. `"xgboost"`) |
| `paper_trading_only` | bool | always true |

Example:

```json
{
  "resolved_count": 2,
  "ab_threshold": 100,
  "ab_ready": false,
  "model_default": "xgboost",
  "paper_trading_only": true
}
```
