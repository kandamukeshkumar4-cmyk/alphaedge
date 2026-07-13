# B2 — Portfolio performance attribution

`GET /api/v1/portfolio/attribution` (JWT) returns top/bottom trades, win rate,
ROI, monthly P&L, and per-category P&L over settled paper trades.

## Double-count guard

Does **not** use E12 `_load_paper_orders` realized_pnl (which adds
`SUM(realized_pnl)` plus settlement CASE). Attribution legs are disjoint:

- SELL → `realized_pnl` only
- Remaining net BUY shares at resolve → settlement PnL once

Math lives in `backend/app/services/analytics_attribution.py`.
