# B4 — Public trade activity feed

- `GET /api/v1/activity/trades` — anonymized paper trades, newest-first, opaque
  offset cursor (`next_cursor`).
- WS: `activity` added to `/api/v1/ws/feed` multiplex hub topics.
- Paper BUY/SELL submit publishes a sanitized frame via
  `publish_paper_trade_activity` (one-line hooks in `orders.py`).
