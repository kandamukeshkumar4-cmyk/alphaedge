# Loop V5 — Backend API Notes (BACKEND TRACK J01-J03)

Additive contracts only. All read/notify surfaces; PAPER_TRADING_ONLY; no order
path. Documented as shipped in worktree `loop-grok-backend`.

## J01 — Watchlist store + API (per JWT user)

Per-user watchlist of market slugs. Table `watchlists` (Alembic
`035_watchlist`, chains from single head `034_venue_market_matches`). Auth via
the existing JWT dependency (`get_current_user`) — **401 when anonymous** on all
three routes. Notify/track only — never an order path.

### POST /api/v1/watchlist

Body: `{ "slug": "nba-2025-01-15-lal-bos" }`

- 201 with the full watchlist (see response shape below).
- Idempotent dedupe: adding a slug already present is a no-op (unique
  constraint `uq_watchlist_user_slug`), still 201 with the current list.
- Unknown slug is honest: **404 `{"detail":"Market not found"}`** when the slug
  has no `Market` row.
- Empty/blank slug → 400.

### DELETE /api/v1/watchlist/{slug}

- 200 with the remaining watchlist. Idempotent: removing a slug not present is a
  no-op 200 (never 404).

### GET /api/v1/watchlist

- 200. Entries newest-first, each composed from the existing market catalog +
  latest odds snapshot + latest prediction. Honest `null` when no data.

Response (shared by all three routes):

```json
{
  "items": [
    {
      "slug": "nba-2025-01-15-lal-bos",
      "title": "Lakers vs Celtics",
      "implied_yes": 0.55,
      "model_prob": 0.62,
      "edge": 0.07,
      "created_at": "2026-07-10T00:00:00Z"
    }
  ],
  "paper_trading_only": true,
  "disclaimer": "Watchlist is notify/track only. Simulated funds — no execution. Not financial advice."
}
```

- `implied_yes` — latest `OddsSnapshot.implied_yes` for the slug, else `null`.
- `model_prob` — latest `PredictionLog.predicted_prob` for the slug, else `null`.
- `edge` — `round(model_prob - implied_yes, 4)`, else `null` when either is
  missing (never fabricated).
