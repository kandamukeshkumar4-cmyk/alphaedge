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

---

## M02 — `GET /api/v1/markets/{slug}/share-snapshot`

A SMALL, read-only intelligence snapshot for one market, sized for an external
share card (frontend `/s/[slug]`). **PUBLIC GET.**

**PATH NOTE (important):** the requested `/api/v1/markets/{slug}/snapshot` path
is **already owned** by the pre-existing FULL market snapshot
(`MarketSnapshotResponse` in `app/api/v1/routes.py`, locked shape + tests, 404 on
unknown slug). Registering a second route on that exact path would shadow /
break the locked contract, violating the additive guardrail. So this compact
share snapshot ships at **`/markets/{slug}/share-snapshot`**. The frontend Z02
share page + Z03 "Share" affordance must target this path.

Reuses the H01 desk composition pieces (`_latest_edge`, `_arb_match`,
`build_smart_money_summary`) and the J02 alert-feed builder, kept compact. Cached
with the desk-cache TTL pattern (in-process `app/core/snapshot_cache.py`, keyed
by slug, gated by the same `DESK_CACHE_ENABLED` / `DESK_CACHE_TTL_SEC` settings;
adds a `cached: bool` flag). Swept by the I01 5xx guard (plain public GET with a
`{slug}` path param — auto-covered).

Fields:

- **`found`** — bool. Unknown slug → honest **200** `{found: false, slug, …nulls}`
  (never a 404).
- **`title`**, **`yes_price`** — from the public market row (`yes_price` honest
  `null` when no odds snapshot).
- **`edge`** — `{model_p, market_p, edge}` or `null` (null when no model
  prediction). `model_p` = latest `PredictionLog.predicted_prob`; `market_p` =
  best reference YES price (asks, else bids; `null` when the book is empty);
  `edge` = the desk `edge_vs_book` (model − book price, `null` without a book).
- **`top_signal`** — `{family, signal_type, created_at, citation}` for the most
  recent alert-family signal on the slug, or `null`. `citation` is the H03 block.
- **`arb_matched`** — bool; a cross-venue (G02) arb match touches this slug.
- **`smart_money_note`** — a short honest one-liner derived from the G07
  aggregate (top-holder share / recent large flows / paper fills), or `null`
  when there is no activity to report (never fabricated).
- **`cached`** — `false` on a freshly built body, `true` when served from the
  TTL cache (rest of the body byte-identical, incl. frozen `generated_at`).

Response (known slug):

```json
{
  "found": true,
  "slug": "nba-2025-01-15-lal-bos",
  "title": "Lakers vs Celtics",
  "yes_price": 0.54,
  "edge": {"model_p": 0.62, "market_p": 0.50, "edge": 0.12},
  "top_signal": {
    "family": "news:mispricing", "signal_type": "news:mispricing",
    "created_at": "2026-07-10T…Z",
    "citation": {"signal_id": "sig-1", "news_id": null,
                 "news_url": "https://example.com/n1",
                 "headline": "Star player questionable",
                 "model_p": 0.62, "market_p": 0.50}
  },
  "arb_matched": false,
  "smart_money_note": "Top 5 wallets hold 40% of open interest; 2 recent large flow(s).",
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Shareable research snapshot — …",
  "generated_at": "2026-07-10T…Z",
  "cached": false
}
```

Unknown slug (HTTP 200): `found:false`, `title/edge/top_signal/smart_money_note`
null, `arb_matched:false`.

Tests: `backend/tests/test_market_share_snapshot_api.py` — known-slug compact
shape (edge one-liner + top-signal citation), unknown honest 200, cache hit
(2nd call `cached:true`, frozen `generated_at`), cache expiry (TTL→0 forces a
rebuild); plus the I01 5xx guard sweep.
