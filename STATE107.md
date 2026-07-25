# STATE107 — PredictionLog production writer + CLV-gated opportunity board

Branch `loop107-predwriter/node`, based on `d614f32` (integration tip, loop106
funnel/empty_reason already present and EXTENDED, not recreated).

## 1. The prediction path I reused (file:line)

No new model was invented. The writer calls the existing chain, unchanged:

| Step | Location |
| --- | --- |
| Writer entrypoint | `backend/app/services/prediction_writer.py:96` `write_model_predictions` |
| Reused predictor facade | `backend/app/services/forecast_service.py:93` `ForecastService.predict` |
| Actual model call | `backend/app/forecasting/predictor.py:60` `predict_market` |
| Provenance capture | `backend/app/services/forecast_service.py:120` `ForecastService._provenance` |
| Feature-schema digest | `backend/app/services/forecast_service.py:59` `feature_schema_digest` |
| Persisted row | `backend/app/db/models.py:604` `PredictionLog` |

`ForecastService.predict(slug, implied_yes=<latest OddsSnapshot.implied_yes>)` is
exactly the call `app/workers/forecast_autolock.py` already makes for external
markets; loop107 applies it to the *catalog* markets the eight PredictionLog
readers query by `market_slug`. Pure quant — no LLM, no NIM, no network model.

## 2. Diagnosis (confirmed against the code)

`PredictionLog` is read by `assistant.py`, `desk.py`, `edge_history.py`,
`market_drivers.py`, `opportunities.py`, `routes.py`, `screener.py`,
`watchlist.py` (plus `app/eval/service.py`, `app/pods/runner.py`,
`app/workers/ops_alerts.py`, `app/workers/data_retention.py`). Before this loop
the only constructor in `app/**` was the model class itself — a table with 12
consumers and zero producers.

Read-only prod re-confirmation (`curl -s
"https://alphaedge-api-production-b9db.up.railway.app/api/v1/opportunities?limit=3"`,
2026-07-25T01:59:27Z, verbatim):

```json
{"opportunities":[],"count":0,"limit":3,"min_liquidity":0,"direction":null,"funnel":{"candidates_scanned":0,"candidates_open":97,"with_model_p":0,"with_market_p":0,"after_min_liquidity":0,"after_direction":0,"returned":0},"empty_reason":"no_model_predictions","paper_trading_only":true,"signal_only":true,...,"generated_at":"2026-07-25T01:59:27.548761+00:00","cached":false}
```

97 open candidates, 0 with a model probability. Nothing deployed or pushed.

## 3. What was built

**`backend/app/services/prediction_writer.py`** (new)
- Candidates: OPEN catalog markets, ordered by `volume desc`, capped at
  `PREDICTION_WRITER_BATCH` (50, hard max 200) — bounded work per pass.
- Gates, each counted rather than faked: `skipped_locked_out` (`lock_at <= now`),
  `skipped_recent` (idempotency — a prediction already exists inside the recency
  window), `skipped_no_market_price` (no persisted odds snapshot to feed the
  predictor), `errors`.
- Row contents are prediction-time only: `market_id`, `market_slug`,
  `predicted_prob`, `confidence`, `odds_snapshot_id` (the exact snapshot used),
  `input_feature_hash`, `explanation {writer, producer, market_implied,
  odds_source, clv_gate_passed, provisional, feature_schema_digest}`,
  `predicted_at = now`, `lock_at = market.lock_at` (the scheduled close).
  `winning_outcome` / `resolved_at` / `MarketResolution` are never read.
- **Forward only.** No backfill exists and none was written: writing historical
  rows from today's data would be look-ahead fabrication.
- Imports no order path (`RiskService` / `OrderBookService` absent).

**Dual wiring**
- In-process: `backend/app/main.py` `_prediction_writer_loop` — boot catch-up
  FIRST (never sleep-first), then `_paced_sleep(1800, ...)`; flag-gated by
  `settings.scheduler_prediction_writer_enabled`; heartbeat `prediction_writer`
  carries the funnel detail.
- ARQ: `backend/app/workers/tasks.py` — import, `functions` entry, and
  `cron(prediction_writer_task, minute={5, 35})` (5 min after the autolock pass;
  overlap is harmless because the task is idempotent per window).
- `prediction_writer_task` records a durable `JobRun` per pass
  (success / degraded / failed), mirroring `forecast_autolock_task`.

**CLV gate — `backend/app/api/v1/opportunities.py`**
- `signal_only` query param, **default true**. A row is listed only when the
  alpha validator's LATEST PERSISTED report
  (`AlphaRun.result["validations"]`, written by `AlphaRunService.run_daily`)
  marks the ranked factor family `model_edge` valid. No statistics are
  recomputed; `app/alpha/**` is read-only and untouched (the gate does not even
  import it — it reads the persisted `AlphaRun` row).
- No `AlphaRun` at all → gate SHUT. Absence of evidence is not evidence of edge.
- Funnel gained `after_signal_gate`; `_opportunities_empty_reason` gained
  `no_validated_edge` (checked after `no_market_prices`, before the liquidity /
  direction reasons). Prod will now report the truth: `with_model_p > 0`,
  `after_signal_gate: 0`, `empty_reason: "no_validated_edge"` — an empty board
  is the CORRECT outcome while the validator rejects `model_edge` (t = -3.19).
- `signal_only=false` shows raw gaps only with `validated: false` on the
  response **and** on every row; the response also carries
  `validated_factor_family: "model_edge"`.
- Cache key now includes `signal_only`, so the two modes cannot bleed.

## 4. Migrations

None. Zero schema change: the writer fills an existing table and the gate is
response-computed. `uv run alembic heads` still reports `066_alpha_validation`
(unchanged), so there is no models-vs-DDL drift to diff.

## 5. Scope notes (declared, not hidden)

- `backend/app/core/config.py` — three additive settings
  (`SCHEDULER_PREDICTION_WRITER_ENABLED` default true, `PREDICTION_WRITER_BATCH`
  50, `PREDICTION_WRITER_WINDOW_SEC` 1800). Required by the dual-wire pattern:
  without a real settings field the ops kill-switch would be fake (a stray env
  var is ignored by the settings model).
- `backend/app/observability/loop_state.py` — one line,
  `"prediction_writer": 1800`, so `GET /api/v1/system/loops` advertises the new
  loop's cadence instead of a blank.
- `backend/tests/test_opportunities_api.py` — the existing 13 tests are intact
  and none were weakened. Two of them plus the shared `_seed` helper now seed
  the validator's PASS branch via `_seed_validator_verdict(valid=True)`, because
  they assert *ranking and filtering*, which is a different contract from
  *validation*. The rejecting branch (production's real state, t = -3.19) is
  covered by the three new gate tests.
- `backend/tests/test_loop105_caller_limits.py` — one seeded `AlphaRun` PASS
  verdict. `test_opportunities_candidate_pool_not_truncated_by_default_limit`
  asserts candidate-POOL breadth, not edge validity; the new default gate
  correctly emptied its board, so the test now states the precondition it
  implicitly relied on. The gate was not relaxed to make it pass.

## 6. NEEDS UI (frontend NOT touched)

- **NEEDS UI:** `/opportunities` must render `empty_reason == "no_validated_edge"`
  as an explicit "no validated edge — the model edge has not beaten the closing
  line out-of-sample" state, distinct from "no model predictions". The existing
  loop106 empty-state copy keys on `empty_reason` and has no branch for this new
  value.
- **NEEDS UI:** rows carry a new boolean `validated`. Any surface that lists
  opportunities with `signal_only=false` must render the `validated: false`
  marker visibly — a raw gap must never be styled like a validated edge.
- **NEEDS UI:** the response `funnel` now has `after_signal_gate`; any funnel
  debug panel should show it between `with_market_p` and `after_min_liquidity`.

## 7. Verbatim tool output (STOP CONDITION)

### `cd backend && uv run --extra dev pytest -q tests/test_loop107_prediction_writer.py tests/test_opportunities_api.py --basetemp=E:/polymarket-worktrees/loop107-predwriter/.pt`

```
....................                                                     [100%]
20 passed in 19.86s
```

(13 pre-existing opportunities tests + 4 new writer tests + 3 new gate tests.)

### `cd backend && uv run --extra dev ruff check app tests`

```
All checks passed!
```

### `cd backend && uv run alembic heads`

```
warning: Failed to hardlink files; falling back to full copy. This may lead to degraded performance.
         If the cache and target directories are on different filesystems, hardlinking may not be supported.
         If this is intentional, set `export UV_LINK_MODE=copy` or use `--link-mode=copy` to suppress this warning.
Installed 83 packages in 14.97s
066_alpha_validation (head)
```

### `cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py tests/test_loop26_authz_matrix.py --basetemp=E:/polymarket-worktrees/loop107-predwriter/.pt2`

```
.....                                                                    [100%]
5 passed in 40.28s
```

Snapshot passed unchanged — no regeneration was required, so
`scripts/regen_openapi_snapshot.py` was NOT run (running it would have been an
unverified edit).

### `cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop107-predwriter/.ptf`

FULL_SUITE_PLACEHOLDER

## 8. Commits

- `5863d8d` feat(loop107): production writer for prediction_logs
- `949b0b9` feat(loop107): dual-wire the prediction writer (in-process loop + ARQ cron)
- `a9304e5` feat(loop107): CLV-gate the opportunity board on the alpha validator verdict
- `bbbd808` test(loop107): seed the validator PASS verdict in the caller-limits pool test
