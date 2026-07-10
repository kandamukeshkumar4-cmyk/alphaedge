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
