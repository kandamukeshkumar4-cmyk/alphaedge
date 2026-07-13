# B5 — Portfolio equity curve snapshots

- Migration `040_portfolio_equity_snapshots` revises `039_order_expiry` (single head).
- Table `portfolio_equity_snapshots`: unique `(user_id, snapshot_date)`.
- Daily ARQ cron `portfolio_equity_snapshot_task` at 00:05; JobRun heartbeat.
- Equity = paper cash + MTM open positions (reuses portfolio helpers).
- `GET /api/v1/portfolio/equity-curve` — ascending date points for the JWT user.
