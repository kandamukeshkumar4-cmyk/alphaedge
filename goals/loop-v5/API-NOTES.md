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

## J02 — Alerts feed

Read-only composition of the existing `signal_events` store — NO new pipeline.

### GET /api/v1/alerts/feed?since=&slugs=&limit=

**Path note:** the pre-existing `GET /api/v1/alerts` (activity.py) returns the
dispatched `Alert` table under a locked shape + test. To stay additive (never
change/remove an existing shape), this feed lives at `/alerts/feed`.

**Public GET** — works anonymously with explicit `slugs`. Optional JWT via the
existing `get_optional_user` dep (a valid token opts into watchlist scoping; an
absent token is anonymous; an invalid token still 401s). Notify/read only —
never touches the order path.

Query params (all optional):

- `since` — ISO-8601 datetime; only events with `created_at >= since`.
- `slugs` — comma-separated slugs; filters `market_id in slugs`.
- `limit` — 1..200, default 50.

Scoping:

- `slugs` given → `scope="explicit"`, filtered to those slugs.
- no `slugs` + authenticated → `scope="watchlist"`, uses the caller's J01
  watchlist (empty watchlist → honest empty `items`).
- no `slugs` + anonymous → `scope="all"`, recent alert-family events.

Alert families surfaced (everything else, e.g. `alignment`/`instability`, is
excluded): `news:mispricing`, `anomaly:unusual_flow`, `arb`, and the prefix
families `delta:*` and `screener:*`. Newest first.

```json
{
  "items": [
    {
      "id": "1b9d...uuid",
      "signal_type": "news:mispricing",
      "platform": "seed",
      "slug": "nba-2025-01-15-lal-bos",
      "headline_eligible": true,
      "created_at": "2026-07-10T00:00:00Z",
      "payload": { "...": "raw SignalEvent payload" },
      "citation": {
        "signal_id": "abc123",
        "news_id": "n1",
        "news_url": "https://example.com/n1",
        "headline": "Star out",
        "model_p": 0.7,
        "market_p": 0.55
      }
    }
  ],
  "slugs": ["nba-2025-01-15-lal-bos"],
  "scope": "explicit",
  "paper_trading_only": true,
  "disclaimer": "Alerts are notify/read only. Research signals — no execution. Simulated funds only. Not financial advice."
}
```

- `citation` = the H03 citation fields lifted from the event payload; every
  field is honest `null` when absent (a `delta:*` event has no news citation).
- Covered by `tests/test_public_get_5xx_guard.py` (force-included via
  `OPTIONAL_AUTH_PUBLIC_GETS` + `MUST_COVER`, since `get_optional_user` marks
  the op with an optional HTTPBearer that the generic sweep would otherwise
  skip).

## J03 — GET /api/v1/system/model-ab (2026-07-10)

Public read-only walk-forward LightGBM-vs-XGBoost A/B readout. Analysis only —
`applied` is ALWAYS false; the deployed default model is never changed. Below
the resolve gate returns `ready:false` with progress; at/above the gate returns
both Briers. Any compute failure degrades to `ready:false` + `note` (never 5xx).

Below threshold:
```json
{"ready": false, "resolved_count": 1, "threshold": 100,
 "lightgbm_available": false, "model_default": "xgboost", "applied": false,
 "paper_trading_only": true}
```
Ready (>=100 resolves):
```json
{"ready": true, "resolved_count": 100, "threshold": 100,
 "lightgbm_available": true, "model_default": "xgboost", "applied": false,
 "xgb_brier": 0.19, "lgbm_brier": 0.18, "delta": -0.01,
 "which_would_win": "lightgbm", "paper_trading_only": true}
```
