# Loop V9 — Backend API notes (backend track N01–N03)

Additive endpoints only. Every route below is a read-only composition of
existing stores — NO new tables, NO migrations, persists nothing, never places
or stores an order. Paper trading only; order path untouched. The opportunity
scanner is a RANKED READ-ONLY VIEW, never an order feed. No fabricated data: a
market with no model probability is EXCLUDED (N01) or honestly null (N02/N03).

---

## N01 — `GET /api/v1/opportunities`

A ranked, read-only view of the markets where the model most disagrees with the
market — "the biggest edges right now" — composed in ONE call. **PUBLIC GET.**

Query params (all optional, bounded):

- **`limit`** (default 20, `1..100`) — max rows returned.
- **`min_liquidity`** (default 0, `>=0`) — liquidity floor; rows with
  `liquidity < min_liquidity` are dropped.
- **`direction`** (`YES`/`NO`, case-insensitive) — keep only rows leaning that
  way. An unrecognized value is ignored (no filter) — never a 422.

Each row:

| field | type | notes |
|-------|------|-------|
| `slug` | string | market slug |
| `title` | string | market title |
| `model_p` | float | model P(YES) — latest `PredictionLog.predicted_prob` (the SAME edge source `/api/v1/desk` (H01) and the M02 share snapshot use) |
| `market_p` | float | market-implied P(YES): best reference YES price from the local order book (asks, else bids — same math as desk/M02), falling back to the odds-snapshot `yes_price` when there is no book |
| `edge` | float | absolute gap `|model_p − market_p|` (the rank key) |
| `direction` | string | `"YES"` when `model_p > market_p` else `"NO"` |
| `yes_price` | float\|null | the market row's displayed YES price (odds snapshot); honest `null` when none |
| `liquidity` | int | market `volume` (the liquidity proxy the catalog ranks by) |
| `top_signal` | object\|null | most-recent alert-family signal on the slug: `{family, citation}` (J02 feed builder + H03 citation), or `null` |

**Ranking:** absolute `edge` desc, then `liquidity` desc, then `slug` (stable).
Only OPEN markets are scored (a resolved market has a known outcome → no edge);
a bounded candidate cap (`_MAX_CANDIDATES = 200`) keeps the public GET bounded.

**Honest exclusions (never faked):** a market with NO model prediction is
excluded; a market with a model but NO market price (empty book AND no odds
snapshot) is excluded (no edge to rank). Empty DB → `opportunities: []`,
`count: 0`.

Cacheable: desk-cache TTL pattern (`app/core/opportunities_cache.py`, gated by
`DESK_CACHE_ENABLED` / `DESK_CACHE_TTL_SEC`), keyed by
`(limit, min_liquidity, direction)`; additive `cached: bool` flag (rest of the
body byte-identical, incl. frozen `generated_at`). Swept by the I01 5xx guard
(added to `MUST_COVER`).

Response:

```json
{
  "opportunities": [
    {
      "slug": "big-edge",
      "title": "Market big-edge",
      "model_p": 0.8,
      "market_p": 0.5,
      "edge": 0.3,
      "direction": "YES",
      "yes_price": 0.5,
      "liquidity": 5000,
      "top_signal": {
        "family": "news:mispricing",
        "citation": {
          "signal_id": "sig-1", "news_id": null,
          "news_url": "https://example.com/n1",
          "headline": "Star player questionable",
          "model_p": 0.8, "market_p": 0.5
        }
      }
    }
  ],
  "count": 1,
  "limit": 20,
  "min_liquidity": 0,
  "direction": null,
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Opportunity scanner — … This is NOT an order feed.",
  "generated_at": "2026-07-10T…Z",
  "cached": false
}
```

Tests: `backend/tests/test_opportunities_api.py` — ranking (highest edge first),
liquidity floor, direction filter, no-model + no-price exclusion, top-signal
present/honest-null, limit bound, honest empty; plus the I01 5xx guard sweep.

---

## N02 — `GET /api/v1/markets/{slug}/drivers`

The top drivers behind the current model probability for ONE market — "why does
the model think this?". **PUBLIC GET.** Composed READ-ONLY from existing stores;
no network (the live news fetcher is NOT called — news catalysts come from the
persisted signal citations).

Query params:

- **`signals_limit`** (default 5, `1..25`) — how many recent alert-family
  signals to surface as drivers.

Fields:

- **`found`** — bool. Unknown slug → honest **200** `{found:false, …nulls,
  drivers:[]}` (never a 404).
- **`model_p`** — latest `PredictionLog.predicted_prob` (desk/M02 edge source),
  or `null`.
- **`market_p`** — best reference YES price from the book (asks, else bids),
  falling back to the odds-snapshot `yes_price`; `null` when neither exists.
- **`gap`** — `model_p − market_p` (signed), or `null` when either is missing.
- **`drivers`** — ordered list. The model-vs-market gap driver first (only when
  `gap` is not null — never faked), then recent alert-family signals. Each
  driver:

  | field | type | notes |
  |-------|------|-------|
  | `label` | string | the signal headline if present, else the family / signal_type; the gap driver is `"Model vs market gap"` |
  | `direction` | string | `"favors YES"` / `"favors NO"` / `"neutral"` (neutral inside the ±0.02 anchor epsilon) |
  | `note` | string | short human note (the gap numbers, or `"<family> signal"`) |
  | `family` | string\|null | alert family for signal drivers; `null` for the gap driver |
  | `citation` | object\|null | H03 citation for signal drivers; `null` for the gap driver |

A known market with no model AND no signals → `{found:true, drivers:[]}`. Swept
by the I01 5xx guard (auto-covered `{slug}` public GET).

Response (known slug):

```json
{
  "found": true,
  "slug": "nba-2025-01-15-lal-bos",
  "model_p": 0.62,
  "market_p": 0.5,
  "gap": 0.12,
  "drivers": [
    {"label": "Model vs market gap", "direction": "favors YES",
     "note": "Model 0.62 vs market 0.5 (+0.1200).", "family": null, "citation": null},
    {"label": "Star player questionable", "direction": "favors YES",
     "note": "news:mispricing signal", "family": "news:mispricing",
     "citation": {"signal_id": "sig-1", "news_id": null,
                  "news_url": "https://example.com/n1",
                  "headline": "Star player questionable",
                  "model_p": 0.62, "market_p": 0.5}}
  ],
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Forecast drivers — …",
  "generated_at": "2026-07-10T…Z"
}
```

Tests: `backend/tests/test_market_drivers_api.py` — known slug with seeded
prediction + news signal (gap driver + signal driver, directions, citation),
unknown honest 200, known slug with no drivers honest empty; plus the I01 5xx
guard sweep.

---

## N03 — `GET /api/v1/markets/{slug}/edge-history`

A bounded time series of `{t, model_p, market_p, edge}` for ONE market, for
charting the model-vs-market edge over time. **PUBLIC GET.** Composed READ-ONLY
from the existing prediction + price logs.

Query params:

- **`window`** (default `7d`) — lenient `<n>h` / `<n>d`, bounded `1h..30d`
  (reuses the L02 `_resolve_window_hours`; an unparseable value falls back to
  the default, never a 422). Only points with `predicted_at >= now − window`
  are returned.

Fields:

- **`found`** — bool. Unknown slug → honest **200** `{found:false, series:[]}`.
- **`window`** / **`window_hours`** — the normalized window echo + its hours.
- **`series`** — ascending-by-`t` list, each point:

  | field | type | notes |
  |-------|------|-------|
  | `t` | datetime | the `PredictionLog.predicted_at` instant |
  | `model_p` | float | `PredictionLog.predicted_prob` at `t` |
  | `market_p` | float\|null | newest `OddsSnapshot.implied_yes` at-or-before `t`; `null` when no snapshot exists yet |
  | `edge` | float\|null | `model_p − market_p` (SIGNED — shows which side the model leaned and when it flipped); `null` when `market_p` is null |

- **`count`** / **`max_points`** — series length and the bound (`200`). When more
  predictions fall in the window than the bound, the MOST RECENT `max_points`
  are kept.

Honest empties: unknown slug OR a known market with no predictions →
`series: []`, `count: 0`. Cacheable (desk-cache TTL, `app/core/opportunities_cache.py`,
key `("edge-history", slug, window)`; additive `cached` flag) and served with the
M03 weak-ETag helper (`ETag` header on 200, `If-None-Match` → 304 empty body;
`generated_at`/`cached` stripped from the hash so a cache hit and a fresh rebuild
of the same content share one validator). Swept by the I01 5xx guard
(auto-covered `{slug}` public GET).

> Note: `edge` here is SIGNED (`model_p − market_p`) for the history chart,
> whereas the N01 scanner row `edge` is the ABSOLUTE gap used as the rank key.

Response:

```json
{
  "found": true,
  "slug": "nba-2025-01-15-lal-bos",
  "window": "7d",
  "window_hours": 168,
  "series": [
    {"t": "2026-07-10T14:00:00+00:00", "model_p": 0.62, "market_p": 0.5, "edge": 0.12},
    {"t": "2026-07-10T16:00:00+00:00", "model_p": 0.7, "market_p": 0.55, "edge": 0.15}
  ],
  "count": 2,
  "max_points": 200,
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Model-vs-market edge history — …",
  "generated_at": "2026-07-10T…Z",
  "cached": false
}
```

Tests: `backend/tests/test_edge_history_api.py` — series shape + ascending order
+ at-or-before market_p join (incl. honest null before the first snapshot),
window bound drops old points, honest empty (unknown slug + known-no-history),
weak-ETag + `If-None-Match` → 304; plus the I01 5xx guard sweep.
