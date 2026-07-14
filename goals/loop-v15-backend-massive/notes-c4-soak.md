# C4 — [LIVE] Connector soak (local Uvicorn)

## Stack

- Docker Desktop daemon unavailable (`dockerDesktopLinuxEngine` named pipe missing)
- Real local Uvicorn `127.0.0.1:8765` + isolated SQLite `backend/c4_soak.db`
- `PAPER_TRADING_ONLY=true`, `LIVE_FEED_ENABLED=false`, all SCHEDULER_* disabled
- **Not** Railway / prod

## Timeline (compressed, DIR-C-001 allows local Uvicorn)

- Server up: 2026-07-13T21:43:37-04:00 (log: Application startup complete)
- Soak window: 2026-07-13T21:44:16.306 → 21:44:30.826-04:00
- Final re-check after gate: see STATE.md Notes

## Live evidence — GET /api/v1/system/sources

| source | state | total_successes | total_failures |
|--------|-------|-----------------|----------------|
| espn-nba | healthy | 5 | 0 |
| worldbank | healthy | 3 | 0 |
| fred | healthy | 0 | 0 |
| polymarket.clob | healthy | 0 | 0 |
| polymarket.gamma | healthy | 0 | 0 |

`count=5`, `paper_trading_only=true`. Admin gate: missing key 422, bad key 401.

## Exceptions

Zero unhandled exceptions in uvicorn soak log. One handled catalog-seed warning:
`Polymarket fetch failed for crypto-btc-friday-5pm ... 404` (isolated, not an API 5xx).

## Gate

`1428 passed, 28 skipped`; ruff All checks passed.
