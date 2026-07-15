# L4 — Local sports multi-league soak (compressed)

## Stack

- Real local Uvicorn `127.0.0.1:8765` + isolated SQLite `backend/l4_soak.db`
- `PAPER_TRADING_ONLY=true`, `LIVE_FEED_ENABLED=false`, all SCHEDULER_* disabled
- `SPORTS_LEAGUES_ENABLED=nba,nfl`
- **Not** Railway / prod; no frontend / deploy config changes

## Timeline (compressed)

- Server up: Application startup complete (uvicorn on :8765)
- Soak window: 2026-07-15T12:47:22.381 → 12:47:24.604 -04:00
- HTTP: `/health` ok paper=true; `/api/v1/sports/results?league=nba` ×5; `?league=nfl` ×5
- All responses `resolves_markets=false` (signals only)

## Live evidence — GET /api/v1/system/sources

| source | state | total_successes | total_failures |
|--------|-------|-----------------|----------------|
| espn-nba | healthy | 5 | 0 |
| espn-nfl | healthy | 5 | 0 |
| polymarket.clob | healthy | 0 | 0 |
| polymarket.gamma | healthy | 0 | 0 |

`count=4`, `paper_trading_only=true`. Admin gate: missing key 422, bad key 401.

## Exceptions

Zero unhandled exceptions in uvicorn soak log. One handled catalog-seed warning
at startup (`Polymarket fetch failed for crypto-btc-friday-5pm ... 404`) — same
as C4, not an API 5xx during soak polls.
