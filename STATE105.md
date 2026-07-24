# Loop 105 — Alpha validation provenance

Date: 2026-07-24

Branch: `loop105-provenance/node`

Implementation commit: `132b8c1 fix(loop105): persist alpha validation provenance`

## Step 1 verdict

**Verdict: Partially correct.**

The orchestrator's central persistence diagnosis was correct: the production
validator had 202 scored LIVE forecasts but no stored closing-line relation and
no immutable per-factor values/provenance. Waiting could not create either
writer. The missing-lock observation is a second, market-specific gap, not the
cause of the validator's existing 202-row population.

The claimed upstream blocker was stale. Production's bridge and autolock loops
are running and the autolock funnel is not at zero.

Read-only production evidence captured 2026-07-24:

```text
GET /api/v1/system/loops
external_market_bridge:
  status=ok
  detail="candidates=25 bridged=8 skipped=17 errors=0"
forecast_autolock:
  status=ok
  detail="external=874 open=658 pre_close=656 in_horizon=11 eligible=2 selectable=2 biggest_drop=3_close_at_in_future->4_within_horizon:645"
paper_trading_only=true
```

Per-stage counts exposed by the deployed heartbeat:

```text
0 external markets total     874
1 status open               658
2 has close_at              unknown in deployed detail; bounded 656..658
3 close_at in future        656
4 within autolock horizon    11
5 lacks LIVE forecast         2
6 after batch cap             2
dominant drop               stage 3 -> 4: 645
```

The deployed formatter does not expose stage 2, so an exact value cannot be
claimed from the public production surface. This change makes future heartbeat
details emit `has_close`, `lacks_live`, and `selectable` explicitly.

```json
GET /api/v1/alpha/latest-signal
{
  "run_date": "2026-07-24",
  "signal": {
    "label": "no signal (evidence)",
    "status": "no_signal",
    "weights": {},
    "residual_alpha_t_stat": null,
    "threshold": 2.5
  },
  "rejection_reasons": [
    {"node": "validator", "factor": "model_edge", "reason": "missing_closing_line"},
    {"node": "validator", "factor": "whale_flow", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "momentum", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "mean_reversion", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "news_sentiment", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "time_decay", "reason": "missing_closing_line"},
    {"node": "validator", "factor": "cross_venue", "reason": "insufficient_factor_provenance"},
    {"node": "portfolio_constructor", "reason": "insufficient_common_oos_returns"}
  ],
  "paper_trading_only": true
}
```

```json
GET /api/v1/alpha/report
{
  "factors": [
    {"name": "model_edge", "valid": false, "reason": "missing_closing_line", "count": 0, "missing_factor_provenance": 0, "missing_closing_line": 202, "t_stat": null},
    {"name": "whale_flow", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "momentum", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "mean_reversion", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "news_sentiment", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "time_decay", "valid": false, "reason": "missing_closing_line", "count": 0, "missing_factor_provenance": 0, "missing_closing_line": 202, "t_stat": null},
    {"name": "cross_venue", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null}
  ],
  "valid_factor_count": 0,
  "paper_trading_only": true
}
```

```json
GET /api/v1/eval/aggregates
{"window_days": 7, "mean_brier": 0.0, "calibration_error": 0.0, "market_count": 0}

GET /api/v1/markets/nba-2025-01-15-lal-bos/locked-forecast
{"slug":"nba-2025-01-15-lal-bos","locked":false,"user_probability":null,"locked_at":null,"market_implied_at_lock":null,"current_market_probability":0.65,"mode":null,"provisional":true,"paper_trading_only":true,"forecast_id":null,"external_market_id":"4999afb0-a695-4aaa-96a2-e52b91458247","empty_reason":"pre_lock"}
```

`market_count: 0` is the separate eval/catalog identity surface. It does not
erase the alpha validator's independently observed 202 scored rows. Likewise,
one canonical market having no lock does not explain why those 202 rows lack
closing lines and five factors lack immutable provenance.

## Implemented

- Added Alembic revision `066_alpha_validation`, chained on
  `065_social_community`.
- Added immutable `alpha_factor_snapshots` keyed by forecast, storing:
  lock-time raw inputs, frozen computed factor values, per-factor provenance,
  capture version, and honest backfill marker.
- Forward capture covers all seven factors. It uses only values timestamped at
  or before the forecast lock. Regime volume is accepted only from the exact
  venue/source identity with `last_synced_at <= locked_at`; Kalshi identity is
  case-normalized.
- Added `alpha_closing_lines`, storing the last observed `odds_snapshots` value
  at or before an explicit market `close_at`. Rows are labelled
  `odds_snapshot_last_pre_close_v1`, `is_estimate=true`; the resolved outcome is
  never a price source. Missing `close_at`, missing odds, and pre-lock-only odds
  remain missing.
- Validator and alpha/regime services now consume persisted values rather than
  recomputing historical factors from mutable/current state.
- Daily alpha execution performs an idempotent provenance backfill before
  validation and continues persisting both signal and no-signal evidence.
- Backfill reconstructs only `model_edge` and `time_decay` from immutable
  ForecastLog columns. `whale_flow`, `momentum`, `mean_reversion`,
  `news_sentiment`, `cross_venue`, and historical regime volume remain
  explicitly `historical_*_not_reconstructible`.
- Closing-line backfill is an explicit derived-estimate policy over real
  pre-close odds. It never derives a price from the outcome.
- Keyset pagination prevents old honest gaps from starving later recoverable
  rows. Unique insert races are isolated with savepoints.
- No alpha import/path to `RiskService` or `OrderBookService` was added.
  `PAPER_TRADING_ONLY` and the residual t-stat threshold `2.5` are unchanged.

## Stop-condition proof

### 1. Touched/impact tests

```text
cd backend
uv run --extra dev pytest -q tests/test_alpha_provenance.py tests/test_alpha_regime_auditor.py tests/test_alpha_run_service.py tests/test_alpha_service.py tests/test_alpha_validation_migration.py tests/test_alpha_validator.py tests/test_autolock_funnel_observability.py tests/test_sentiment_debate.py --basetemp=E:/polymarket-worktrees/loop105-provenance/.pt

..............................                                           [100%]
30 passed in 20.58s
```

### 2. Ruff

```text
cd backend
uv run --extra dev ruff check app tests

All checks passed!
```

### 3. Local alpha run against populated history

```text
cd backend
uv run --extra dev pytest -q -s tests/test_alpha_provenance.py -k statistical --basetemp=E:/polymarket-worktrees/loop105-provenance/.pt-json-final
```

```json
{"paper_trading_only": true, "provenance_backfill": {"closing_line_gaps": 0, "closing_lines": 20, "factor_snapshots": 20, "scanned": 20}, "status": "no_signal", "validations": [{"bootstrap_lower": 0.0425, "brier_delta_vs_closing": 0.0425, "closing_brier": 0.2025, "correlation_clusters": 20, "count": 20, "is_brier": 0.16, "missing_closing_line": 0, "missing_factor_provenance": 0, "name": "model_edge", "oos_brier": 0.16, "oos_count": 8, "oos_degradation": 0.0, "reason": null, "t_stat": 999.0, "valid": true}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "whale_flow", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "momentum", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "mean_reversion", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "news_sentiment", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"bootstrap_lower": -0.038354, "brier_delta_vs_closing": -0.038354, "closing_brier": 0.2025, "correlation_clusters": 20, "count": 20, "is_brier": 0.240854, "missing_closing_line": 0, "missing_factor_provenance": 0, "name": "time_decay", "oos_brier": 0.240854, "oos_count": 8, "oos_degradation": 0.0, "reason": "oos_does_not_beat_closing", "t_stat": -999.0, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "cross_venue", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}]}
```

```text
1 passed, 8 deselected in 8.68s
```

The two truthfully reconstructible factors now reach statistical evaluation:
`model_edge` validates and `time_decay` is honestly rejected with
`oos_does_not_beat_closing`. The other five remain honestly absent historically
and accumulate only from forward capture.

### 4. Full backend suite

```text
cd backend
uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop105-provenance/.pt-full

2102 passed, 28 skipped in 526.07s (0:08:46)
```

### 5. Migration head

```text
cd backend
uv run alembic heads

066_alpha_validation (head)
```

### 6. Orchestration gate

The first gate invocation passed backend pytest/Ruff but found this worktree
without `frontend/node_modules`; `tsc`, `vitest`, and `next` were not installed.
`npm ci` restored the exact lockfile dependencies without changing manifests.
The single gate retry passed:

```text
py -3.13 orchestration/gate.py

=== GATE: backend pytest ===
2102 passed, 28 skipped in 565.70s (0:09:25)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
Test Files  101 passed (101)
Tests  567 passed (567)
PASS frontend test (exit 0)

=== GATE: frontend build ===
Compiled successfully
Generating static pages (117/117)
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

Pytest emitted Windows temporary-directory cleanup warnings after completion;
they did not change any check exit code or the final gate verdict.

## Contract, review, and scope gates

- Endpoint route/request/response schemas did not change. OpenAPI regeneration
  and `AUTH_CLASS`/authz-matrix count updates are not applicable.
- `requesting-code-review` was not callable in this environment. Manual
  line-by-line diff review plus two independent reviewer lanes were used as the
  documented fallback. Both final verdicts: `APPROVED`.
- Bumblebee supply-chain scan: not applicable. No manifest, lockfile,
  dependency loader, or deployment-image file changed. `npm ci` left the
  tracked dependency inventory unchanged.
- No push and no deploy were performed.
- Preserved/excluded non-node state:
  `SCOUT105-PROVENANCE.md`, `grok-audit-provenance.txt`,
  `sol-prompt.txt`, `sol105.log`.

AutoLab: baseline=35 provenance-path tests green but production validator had 0 usable rows and missing_* rejections | benchmark=local daily alpha JSON plus full gate | iterations=4, best=20/20 truthful reconstructible rows reach statistical verdicts | budget=4/4 | outcome=improved

## git log --oneline

```text
132b8c1 fix(loop105): persist alpha validation provenance
736e92d merge(loop104): traders + library dead routes now live surfaces (Sol)
0a46ad6 docs(loop104): record route proof and review
3198374 docs(loop105): provenance scout — alpha blocked upstream at the autolock funnel
45bdb84 merge(loop104): social/community backend (Cursor; Grok audit PASS WITH FIXES, blocker fixed)
fe5c2bc fix(loop104): stable composite cursor for story pagination
a86897f fix(loop104): make loading proofs deterministic
b46895f fix(loop104): minimize live read credentials
9e4b589 feat(loop104): turn library into live research archive
e791ff8 feat(loop104): ship live trader rankings and detail
```
