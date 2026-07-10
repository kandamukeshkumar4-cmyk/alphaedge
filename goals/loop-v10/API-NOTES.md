# Loop V10 — Backend API notes (backend track O01–O03)

Additive endpoints only. Every route below is a read-only composition of
existing stores — NO new tables, NO migrations, persists nothing, never places
or stores an order. Paper trading only; order path untouched. No fabricated
data: resolved review uses ONLY real resolutions; unknown slugs/categories are
honestly `{found:false}` / zeros; honest empties everywhere.

---

## O01 — `GET /api/v1/resolved`

A browsable, PUBLIC GET list of RESOLVED external markets with the model's
prediction vs the actual outcome — the public track record. Composed READ-ONLY
from the SAME resolved-forecast source as `/api/v1/track-record` and
`/api/v1/backtest/summary` (`ForecastLog` x `ForecastScore` x `ExternalMarket`,
`mode=LIVE`, `status=RESOLVED`). **No invented outcomes — only real resolutions.**

Query params (bounded pagination):

- **`limit`** (default 50, `1..200`) — max rows per page.
- **`offset`** (default 0, `>=0`) — page offset.

One row **per resolved external market**. `ExternalMarket` has no dedicated slug
column, so `external_id` is the stable per-market key (same convention as the
K01 self-serve backtest). The model probability at close is the **latest** LIVE
forecast on the market (max `seq` then `locked_at`) before resolution.

Each row:

| field | type | notes |
|-------|------|-------|
| `slug` | string | `ExternalMarket.external_id` |
| `title` | string | market title |
| `resolved_at` | datetime\|null | `ExternalMarket.resolved_at` (ISO) |
| `outcome` | string | `"YES"` when the real outcome resolved YES else `"NO"` (`ForecastScore.actual_outcome`) |
| `model_p_at_close` | float | the latest LIVE forecast's `user_probability` |
| `correct` | bool | `(model_p_at_close >= 0.5) == (outcome == YES)` |
| `brier` | float | `(model_p_at_close − outcome_int)²` |

Summary header (over ALL resolved markets, not just the page):

| field | type | notes |
|-------|------|-------|
| `n` | int | number of resolved markets |
| `accuracy` | float\|null | share of markets the model called correctly (`null` at `n=0`) |
| `mean_brier` | float\|null | mean per-market Brier (`null` at `n=0`) |
| `thin_data` | bool | `n < 30` (same threshold as track-record, `BRIER_MIN_SAMPLE`) |
| `thin_data_threshold` | int | `30` |

Rows ordered newest-resolution-first (null `resolved_at` last), then `slug`
(stable). Non-finite probabilities (Postgres NUMERIC `NaN`) are dropped so the
Brier math never 500s. Honest empty → `{rows: [], summary: {n:0, accuracy:null,
mean_brier:null, thin_data:true, ...}}`. Cacheable (desk-cache TTL via
`opportunities_cache`, key `("resolved", limit, offset)`; additive `cached`
flag) and served with the M03 weak-ETag (`ETag` on 200, `If-None-Match` → 304).
Added to the I01 5xx guard `MUST_COVER`.

Response:

```json
{
  "rows": [
    {"slug": "mkt-d", "title": "Market mkt-d",
     "resolved_at": "2026-07-10T14:00:00+00:00", "outcome": "NO",
     "model_p_at_close": 0.6, "correct": false, "brier": 0.36}
  ],
  "summary": {"n": 4, "accuracy": 0.75, "mean_brier": 0.1225,
              "thin_data": true, "thin_data_threshold": 30},
  "count": 1,
  "limit": 50,
  "offset": 0,
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Resolved-market review — …",
  "generated_at": "2026-07-10T…Z",
  "cached": false
}
```

Tests: `backend/tests/test_resolved_review_api.py` — seeded resolutions →
correct rows + accuracy + mean_brier, honest empty, pagination offset/limit;
plus the I01 5xx guard sweep.

---

## O02 — `GET /api/v1/categories/{category}/summary`

A PUBLIC GET per-category intelligence aggregate, composed READ-ONLY from
existing surfaces. The category is matched via the app's EXISTING taxonomy
(`MarketService._catalog_category_filter` — the same filter Discover/markets
use). The path segment is case-sensitive to the taxonomy: lowercase API slugs
(`sports`, `politics`, `crypto`, `culture`, `economics`, `weather`, `tech`,
`nfl`) and capitalized legacy values (`NBA`, `FIFA WC2026`, `Elections`) are
recognized; any other string falls back to an exact `Market.category` match.

Fields:

| field | type | notes |
|-------|------|-------|
| `category` | string | the requested category (echoed, trimmed) |
| `found` | bool | `true` when the category has ≥1 local market OR ≥1 resolved market; else honest `false` |
| `market_count` | int | local catalog markets in the category |
| `mean_abs_edge` | float\|null | mean absolute model-vs-market edge across the category's OPEN markets that have both a model prob and a market price; `null` when none |
| `top_opportunities` | list | up to 3 N01 opportunity rows (same shape: `slug/title/model_p/market_p/edge/direction/yes_price/liquidity/top_signal`), ranked by edge |
| `recent_signal_count` | int | alert-family `signal_events` on the category's markets in the last 7 days |
| `resolved_n` | int | resolved markets in the category (O01 review filtered by `ExternalMarket.category`, case-insensitive) |
| `resolved_accuracy` | float\|null | model accuracy over those resolved markets; `null` when `resolved_n=0` |

Note on taxonomy: the local catalog and the resolved-market (`ExternalMarket`)
category fields are independent freeform strings. A category that matches BOTH
(e.g. `"NBA"`) yields non-zero `market_count` AND `resolved_n`; a lowercase API
alias like `"sports"` scopes the local catalog but only matches resolved markets
whose `ExternalMarket.category` is literally `"sports"`. No fabrication — each
side is scoped honestly and independently.

Unknown/empty category → honest `{found:false, market_count:0, mean_abs_edge:
null, top_opportunities:[], recent_signal_count:0, resolved_n:0, resolved_
accuracy:null}`. Cacheable (desk-cache TTL via `opportunities_cache`, key
`("category-summary", category.lower())`; additive `cached` flag). Swept by the
I01 5xx guard (the guard now satisfies `{category}` with a known + unknown
category; `/api/v1/categories/Sports/summary` is in `MUST_COVER`).

Response (known category):

```json
{
  "category": "NBA",
  "found": true,
  "market_count": 1,
  "mean_abs_edge": 0.3,
  "top_opportunities": [
    {"slug": "nba-cat-lal-bos", "title": "Lakers vs Celtics", "model_p": 0.8,
     "market_p": 0.5, "edge": 0.3, "direction": "YES", "yes_price": 0.5,
     "liquidity": 5000, "top_signal": {"family": "news:mispricing", "citation": {…}}}
  ],
  "recent_signal_count": 1,
  "resolved_n": 1,
  "resolved_accuracy": 1.0,
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Category intelligence — …",
  "generated_at": "2026-07-10T…Z",
  "cached": false
}
```

Tests: `backend/tests/test_category_summary_api.py` — known-category aggregate
(market_count, mean_abs_edge, top opportunity, recent signals, resolved n +
accuracy), unknown honest, empty/whitespace honest; plus the I01 5xx guard sweep.

---
