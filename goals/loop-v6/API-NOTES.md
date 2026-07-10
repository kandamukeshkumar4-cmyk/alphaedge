# Loop V6 — API Notes (backend track K01–K03)

Additive endpoints only. Every route below is read-only composition of
existing stores (no new tables/migrations, no order path). Paper trading only.

---

## K01 — `GET /api/v1/backtest/run?slug=`

Self-serve, deterministic walk-forward Brier + flat-stake ROI for **ONE**
market's resolved forecast history. **PUBLIC GET**, read-only, bounded compute.
Reuses the same resolved-forecast source and bet math as `/backtest/summary`
(`ForecastLog` → `ForecastScore` on a RESOLVED `ExternalMarket`), scoped to a
single market.

- **`slug`** identifies the market via `ExternalMarket.external_id` (that model
  has no dedicated slug column; `external_id` is the stable per-market key).
- Bounded: at most 5,000 forecast rows processed per call.
- **Never 5xx.** Any failure — unknown slug, too few resolves, or a compute
  error — degrades to an honest `{ran: false, reason, slug}` at HTTP 200. This
  route is swept by the I01 public-GET 5xx guard (required `slug` query param is
  auto-filled from the guard's seeded markets, which are non-external, so the
  guard exercises the `unknown_slug` not-ran path).
- Minimum to run: `BACKTEST_RUN_MIN_SAMPLE = 3` scored resolved forecasts on the
  market. Below that → `ran:false, reason:"too_few_resolves"`.
- `thin_data` is true while `n < 30` (`BRIER_MIN_SAMPLE`) even when it runs.

`reason` values (only when `ran:false`): `empty_slug`, `unknown_slug`,
`too_few_resolves`, `compute_error`.

Response (`BacktestRunSlugResponse`):

```json
{
  "ran": true,
  "slug": "mkt-good",
  "reason": null,
  "n": 3,
  "thin_data": true,
  "thin_data_threshold": 30,
  "brier_score": 0.046667,
  "market_brier_score": 0.22,
  "roi": 0.875,
  "n_bets": 3,
  "total_pnl": 1.4,
  "total_staked": 1.6,
  "walk_forward": [
    {"seq": 1, "scored_at": "2026-07-10T...Z", "brier": 0.09,
     "cumulative_brier": 0.09, "cumulative_roi": 1.0}
  ],
  "source": "forecast_scores",
  "last_updated": "2026-07-10T...Z",
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Self-serve walk-forward research metrics ..."
}
```

Honest not-ran body (HTTP 200):

```json
{
  "ran": false, "slug": "does-not-exist", "reason": "unknown_slug",
  "n": 0, "thin_data": true, "thin_data_threshold": 3,
  "brier_score": null, "market_brier_score": null, "roi": null,
  "n_bets": 0, "total_pnl": 0.0, "total_staked": 0.0,
  "walk_forward": [], "source": "none", "last_updated": null,
  "paper_trading_only": true, "signal_only": true, "disclaimer": "..."
}
```

Tests: `backend/tests/test_backtest_run_slug_api.py` (known-market runs,
unknown-slug honest not-ran, below-min-sample not-ran, empty-slug not-ran) plus
coverage under `tests/test_public_get_5xx_guard.py`.

---

## K02 — `GET /api/v1/portfolio/clv-summary`

**AUTHED (JWT — 401 when anonymous).** Realized closing-line-value distribution
for the **caller's SETTLED paper orders**, composed from two existing modules:

* the caller's `PaperOrder` ledger (per-user entry price + side + slug), and
* `CLVTrackingService.get_clv_track_record()` for the resolved closing line
  (YES implied) per `market_slug`, scored with the canonical
  `app.backtesting.clv.closing_line_value` (same-side: `closing - entry`).

Per settled order: `side=order.outcome` (`yes`/`no`); YES CLV =
`closing_yes - entry`, NO CLV = `(1 - closing_yes) - entry`. Orders whose slug
has no resolved closing line are skipped (no fabrication). Read-only — persists
nothing, no order path. Honest empty (`count:0`, null `mean`/`positive_share`,
zeroed histogram) when the caller has no settled orders (`source:"none"`) or no
settled order matches a resolved closing line (`source:"paper_orders"`).

Histogram bins (fixed, CLV = closing − entry): `<= -0.10`, `-0.10..-0.05`,
`-0.05..0.00`, `0.00..0.05`, `0.05..0.10`, `>= 0.10`.

Response (`PortfolioClvSummaryResponse`):

```json
{
  "count": 2,
  "mean": 0.1,
  "positive_share": 1.0,
  "total_clv": 0.2,
  "histogram": [
    {"label": "<= -0.10", "lo": null, "hi": -0.1, "count": 0},
    {"label": "0.05..0.10", "lo": 0.05, "hi": 0.1, "count": 1},
    {"label": ">= 0.10", "lo": 0.1, "hi": null, "count": 1}
  ],
  "matched_slugs": 2,
  "settled_orders": 2,
  "source": "paper_orders",
  "paper_trading_only": true,
  "disclaimer": "Realized closing-line value on SETTLED paper trades only. ..."
}
```

Anon → `401`. Honest empty body has `count:0`, `mean:null`,
`positive_share:null`, `total_clv:0.0`, all histogram bins `count:0`.

Tests: `backend/tests/test_portfolio_clv_summary_api.py` (401 anon, empty-honest,
seeded YES+NO distribution with unsettled-order exclusion, settled-without-closing
honest empty).

## K03 — GET /api/v1/watchlist/alerts (2026-07-10)

Authed (JWT). The J02 alerts feed pre-filtered to the caller's watchlist slugs.
401 anon; honest empty `{items: []}` when the watchlist is empty. Items use the
same `AlertFeedItem` shape as `/api/v1/alerts/feed` (slug-keyed + citation).
