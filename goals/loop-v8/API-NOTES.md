# Loop V8 — API Notes (backend track M01–M03)

Additive endpoints/headers only. Every route below is a read-only composition of
existing stores — NO new tables, NO migrations, persists nothing, never places
or stores an order. Paper trading only; order path untouched.

---

## M01 — `GET /api/v1/home`

Personalized intelligence landing composed in ONE call from existing services,
so the home page renders without a fan-out of per-widget requests.

**PUBLIC GET with OPTIONAL JWT** (`get_optional_user`). Anonymous callers get the
four non-personal sections; a valid token ALSO enriches with the caller's K03
watchlist. An *invalid* token still 401s (optional-auth contract); absence of a
token is anonymous. Read-only composition — no new pipeline/table, persists
nothing. Swept by the I01 5xx guard (added to `MUST_COVER` +
`OPTIONAL_AUTH_PUBLIC_GETS`).

Query params (all optional, bounded):

- **`signals_limit`** (default 5, `1..25`) — number of recent signals AND
  recent watchlist alerts.
- **`markets_limit`** (default 5, `1..25`) — number of top markets.
- **`digest_window`** (default `24h`) — passed to the L02 digest (same lenient
  `<n>h`/`<n>d` parsing + `1h..30d` bounds; unparseable falls back to `24h`).

Sections:

- **`signals`** — top-N most recent alert-family `SignalEvent`s, newest first,
  each carrying the H03 `citation` block (`signal_id`, `news_id`, `news_url`,
  `headline`, `model_p`, `market_p` — honest `null` when absent). Reuses the J02
  `_build_alert_feed` builder (`scope="all"`, no slug filter).
- **`digest`** — the full L02 `AlertsDigestResponse` (families counts,
  `top_movers`, `total`, `window`, `window_hours`, `since`). Reuses
  `get_alerts_digest` verbatim.
- **`model_ab`** — I02/J03 readiness numbers only (cheap; the heavy walk-forward
  A/B is NEVER run on a home render): `resolved_count`, `ab_threshold`,
  `ab_ready`, `model_default`, `lightgbm_available`, `applied` (always `false`
  — the deployed default model is never flipped here).
- **`top_markets`** — highest-liquidity public markets (volume is the liquidity
  proxy the catalog already ranks by), compact
  `{slug, title, category, volume, yes_price, status}`, volume desc. Reuses
  `MarketService.list_public_markets(sort="volume")`.
- **`watchlist_count`** / **`watchlist_alerts`** — authed only. Anonymous →
  `watchlist_count: null`, `watchlist_alerts: []`. Authed → the caller's K03
  watchlist size + the J02 alert feed pre-filtered to the watchlist slugs (same
  `AlertFeedItem` shape as `signals`).

Response:

```json
{
  "authenticated": false,
  "signals": [
    {
      "id": "…", "signal_type": "news:mispricing", "platform": "seed",
      "slug": "nba-2025-01-15-lal-bos", "headline_eligible": true,
      "created_at": "2026-07-10T…Z", "payload": { … },
      "citation": {
        "signal_id": "sig-1", "news_id": "n-1",
        "news_url": "https://example.com/n1",
        "headline": "Star player questionable",
        "model_p": 0.62, "market_p": 0.50
      }
    }
  ],
  "digest": { "families": {"news:mispricing": 1, "arb": 1}, "top_movers": [ … ],
              "window": "24h", "window_hours": 24, "since": "…",
              "slugs": null, "total": 2, "paper_trading_only": true,
              "disclaimer": "…" },
  "model_ab": { "resolved_count": 0, "ab_threshold": 50, "ab_ready": false,
                "model_default": "xgboost", "lightgbm_available": true,
                "applied": false },
  "top_markets": [
    {"slug": "nba-2025-01-16-gsw-mia", "title": "B", "category": "Sports",
     "volume": 9000, "yes_price": null, "status": "open"}
  ],
  "watchlist_count": null,
  "watchlist_alerts": [],
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Personalized intelligence home — …",
  "generated_at": "2026-07-10T…Z"
}
```

Honest empty DB (HTTP 200): `signals: []`, `digest.total: 0`,
`digest.families: {}`, `top_markets: []`, `watchlist_count: null`,
`watchlist_alerts: []`.

Tests: `backend/tests/test_home_api.py` — anon shape (personal sections
nulled/empty, H03 citation carried, top-markets volume-desc, digest total),
authed enrichment (watchlist count + watchlist-scoped alert), honest empty DB;
plus the I01 5xx guard sweep.
