# B1 — Public leaderboard (completed)

`GET /api/v1/leaderboard` ranks JWT users by settled paper-trade performance.

## Behavior

- Metrics: `realized_pnl` (settlement formula unchanged), `win_rate`, `roi` (= PnL / settled cost).
- Query: `sort=realized_pnl|roi|win_rate`, `limit` (1–100, default 20), `offset`.
- Response adds `total`, `sort`, `cached` (additive; existing entry fields preserved).
- Display names: `users.display_name` if set, else stable `Trader-{sha256[:6]}` (no email leak).
- Users with zero settled trades are excluded.
- In-process TTL cache: `app.core.leaderboard_cache` (5s), same pattern as desk/opportunities caches.

## Files

- `backend/app/api/v1/leaderboard.py` — route
- `backend/app/services/analytics_leaderboard.py` — ranking math
- `backend/app/core/leaderboard_cache.py` — TTL cache
- `backend/app/schemas/leaderboard.py` — additive fields
- `backend/tests/test_leaderboard.py` — math + HTTP coverage
