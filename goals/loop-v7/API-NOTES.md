# Loop V7 — API Notes (backend track L01–L03)

Additive endpoints/params only. Every route below is read-only composition of
existing stores, except L03 which adds ONE new table (notify prefs, stored +
read in-app only — NO external delivery). Paper trading only; order path
untouched.

---

## L01 — `GET /api/v1/backtest/run?slug=&edge_threshold=&stake=`

Extends the K01 self-serve per-market walk-forward backtest with two OPTIONAL,
deterministic, read-only strategy params. **PUBLIC GET.** Everything K01
documented (goals/loop-v6/API-NOTES.md) still holds — same
`BacktestRunSlugResponse` shape, same honest `{ran:false}` paths, still swept by
the I01 5xx guard.

New OPTIONAL query params:

- **`edge_threshold`** (float, default unset): minimum `|model_p - market_p|`
  edge required to place a paper bet. Clamped to `[0.0, 1.0]`. Floored at the
  anchor epsilon (`ANCHOR_EPSILON = 0.02`) so `edge_threshold` only ever RAISES
  the bet gate — near-zero-edge noise bets are never fabricated. Unset (or a
  value ≤ epsilon) reproduces K01's gate exactly.
- **`stake`** (float, default `1.0`): flat stake per bet. Scales `total_staked`
  and `total_pnl` by the same factor, so `roi` (which cancels the factor) is
  stake-invariant. Clamped to `[0.01, 1000.0]`.

Clamp behavior: out-of-range values **clamp** (never 422/5xx). e.g.
`stake=99999 → 1000.0`, `stake=0 → 0.01`, `edge_threshold=5 → 1.0`.

Invariants:

- Omitting BOTH params (or passing the documented defaults `stake=1.0` with no
  `edge_threshold`) reproduces K01's response body **byte-for-byte** — the
  params are purely additive. Regression test asserts `plain == with_defaults`.
- `brier_score` / `market_brier_score` / `n` are over ALL scored forecasts and
  are **unaffected** by these params. Only `n_bets`, `total_staked`,
  `total_pnl`, `roi`, and the per-point `cumulative_roi` respond.
- Response shape is unchanged (no new fields), preserving the byte-for-byte
  guarantee and K01's contract.

Example (`mkt-good`: three forecasts, diffs 0.2/0.2/0.4, all resolve YES):

| call | n_bets | total_staked | total_pnl | roi |
|------|--------|--------------|-----------|-----|
| `?slug=mkt-good` (K01 default) | 3 | 1.6 | 1.4 | 0.875 |
| `?slug=mkt-good&stake=10` | 3 | 16.0 | 14.0 | 0.875 |
| `?slug=mkt-good&edge_threshold=0.3` | 1 | 0.5 | 0.5 | 1.0 |
| `?slug=mkt-good&edge_threshold=5` (clamped→1.0) | 0 | 0.0 | 0.0 | null |

Tests: `backend/tests/test_backtest_run_slug_api.py` — `test_default_params_
reproduce_k01_byte_for_byte`, `test_edge_threshold_filters_bets`,
`test_stake_scales_pnl_and_staked_roi_invariant`, `test_out_of_range_params_
clamp`, plus the existing K01 cases and the I01 5xx guard sweep.

---

## L02 — `GET /api/v1/alerts/digest?window=24h&slugs=&top=5`

Per-family alert counts + top-N most-alerted markets over a bounded lookback
window. **PUBLIC GET** (anonymous), read-only composition of the existing
`signal_events` store — NO new pipeline, never places or stores an order.
Covered by the I01 5xx guard (added to `MUST_COVER`).

Query params:

- **`window`** (default `24h`): lookback, `<n>h` or `<n>d` (e.g. `24h`, `7d`).
  Bounded to `[1h, 30d]`. **Lenient**: an unparseable/empty window falls back to
  `24h` and an out-of-range one clamps (never 422/5xx). Echoed back normalized
  in the requested unit as `window` (+ `window_hours` integer, + `since` ts).
- **`slugs`** (optional): comma-separated slug filter. Explicit-but-empty →
  honest empty digest.
- **`top`** (default 5, `1..50`): size of the `top_movers` ranking.

The five families (matching the J02 feed families): `news:mispricing`,
`anomaly:unusual_flow`, `delta:*`, `screener:*`, `arb`. `delta:` and `screener:`
sub-types collapse into the `delta:*` / `screener:*` family buckets. Non-family
signal types are ignored.

`top_movers` ranks markets by **`signal_count`** — the number of alert-family
signals the market generated in the window (the honest activity/movement proxy
available from the signal store; NOT a fabricated price move). Ordering:
`signal_count` desc, then most-recent signal desc, then slug asc (deterministic).

Response (`AlertsDigestResponse`):

```json
{
  "families": {"news:mispricing": 1, "delta:*": 2, "arb": 1},
  "top_movers": [
    {"slug": "nba-2025-01-15-lal-bos", "signal_count": 3,
     "families": {"news:mispricing": 1, "delta:*": 2},
     "last_signal_at": "2026-07-10T...Z"}
  ],
  "window": "24h",
  "window_hours": 24,
  "since": "2026-07-09T...Z",
  "slugs": null,
  "total": 4,
  "paper_trading_only": true,
  "disclaimer": "Alerts are notify/read only. ..."
}
```

Honest empty (HTTP 200): `families: {}`, `top_movers: []`, `total: 0`, with
`window`/`window_hours`/`since` still populated.

Tests: `backend/tests/test_alerts_digest_api.py` — family counts + window
filter, wider-window inclusion, top-movers ordering, slug filter, honest empty,
default/invalid/out-of-range window handling; plus the I01 5xx guard sweep.
