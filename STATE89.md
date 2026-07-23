# Loop 89 - Accuracy-gate diagnosis (2026-07-23)

## 1. Accuracy gate verdict - B: scoring is healthy, but the A/B verdict was silently unwired

Production is not merely waiting on outcomes. Resolution and autolock are
healthy and grow the real population, but no caller refreshed
`refresh_controlled_ab_readout`. Crossing 100 clusters would therefore still
leave `GET /api/v1/system/model-ab` at `controlled_readout_not_refreshed`.

### Production evidence (read-only; no deploy)

At 2026-07-23 19:10Z, `GET /api/v1/system/resolved-count` returned:

```json
{"resolved_count":175,"forecast_scored_count":175,"correlation_clusters":93,"ab_threshold":100,"ab_ready":false,"default_model":"xgboost","lightgbm_available":true}
```

At the same time, `GET /api/v1/system/loops` showed:

```json
[
  {"name":"external_resolve","running":true,"status":"ok","last_heartbeat":"2026-07-23T19:03:29.73996Z","interval_sec":900},
  {"name":"forecast_autolock","running":true,"status":"ok","last_heartbeat":"2026-07-23T19:03:31.09418Z","interval_sec":900,"detail":"external=827 open=642 pre_close=637 in_horizon=18 eligible=4 selectable=4 ..."}
]
```

`GET /api/v1/calibration/latest` returned
`{"markets_evaluated":175,"brier_score":0.06658161325714286,"calibration_error":0.1958615352532019,"gate":"pass","paper_trading_only":true}`.
`GET /api/v1/system/model-ab` returned
`{"ready":false,"note":"controlled_readout_not_refreshed","model_default":"xgboost","lightgbm_available":true}`.

Code trace: `resolve_external_markets` -> `ScoringService` -> `ForecastScore`;
`load_forecast_score_rows` derives cluster IDs from resolved external markets.
The existing `external_resolve` and `forecast_autolock` in-process loops are
not dead ARQ-only jobs.

Rate / ETA: the claimed ~40 clusters/week is not in a persisted production time
series, so it is unproven. Current deficit is **7 clusters**. Conditional on
that claimed rate, the ETA is **1.23 days**; do not treat it as an observed
forecast.

### Repair

Commit: `ca9a16a fix(loop89): refresh controlled accuracy readout`

- Adds `refresh_forecast_model_ab_task`: explicit pre-gate skip, then persists
  a controlled cached readout only after 100 clusters.
- Dual-wires an hourly in-process loop and ARQ cron fallback, with public
  `forecast_model_ab` heartbeat detail.
- Adds default-on non-secret `SCHEDULER_FORECAST_MODEL_AB_ENABLED`.
- Does not change `ml_model_type`, apply a winner, create orders, or touch the
  `RiskService -> OrderIntent -> OrderBookService` path.

Proof:

```text
cd backend && uv run --extra dev pytest -q tests/test_forecast_model_ab_task.py tests/test_model_ab_harness.py tests/test_model_ab_endpoint.py tests/test_system_resolved_count.py tests/test_loop_intervals.py tests/test_heartbeat_guards.py --basetemp=E:/polymarket-worktrees/loop89-sol/.pt
18 passed in 35.05s
uv run --extra dev ruff check app tests
All checks passed!
```

NEEDS USER / orchestrator after deploy: the harness also deliberately refuses
historic comparison until `AB_MODEL_TYPE_HISTORY_VERIFIED` and non-secret
`AB_MODEL_TYPE_HISTORY_EVIDENCE` are supplied. Railway has no explicit value,
so the safe default is false. Existing population reports
`provenance_model_types=["implied_passthrough"]` and 143 missing historical
model versions/artifact digests. Do not assert a winner until this requirement
and the post-deploy >=100-cluster heartbeat are both satisfied.

## 2. Secondary production QA / compiler repair

Read-only production sweep: `/health`, `/signals/dashboard`, `/feed`,
`/briefs`, `/skills/`, `/scanners/`, `/screener`, and `/usage/summary` all
returned HTTP 200. Health and signals returned `paper_trading_only:true`; no
5xx or paper-execution leak was observed.

Found bug: `POST /api/v1/scanners/compile` timed out twice for harmless preview
`Find high-volume sports markets`: at 30 seconds and again at 90 seconds. Its
10-second provider timeout excluded waiting on the shared LLM semaphore.

Commit: `57d7245 fix(loop89): bound scanner compile queue wait`

- Bounds semaphore acquisition plus LLM call with the existing 10-second budget
  and returns the existing deterministic fallback on timeout.
- Adds a held-semaphore regression test, alongside the existing slow-provider
  timeout test.

Proof:

```text
cd backend && uv run --extra dev pytest -q tests/test_scanner_llm_planner.py --basetemp=E:/polymarket-worktrees/loop89-sol/.pt
8 passed in 6.50s
uv run --extra dev ruff check app tests
All checks passed!
```

## 3. Final verification / review

```text
cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop89-sol/.ptf
1998 passed, 28 skipped in 377.36s (0:06:17)
```

Manual changed-line review: PASS. The A/B task writes only a cached `JobRun`,
skips pre-gate work, and exposes a heartbeat; it cannot change model selection
or the order path. The compiler repair only brings semaphore acquisition under
the existing fallback timeout.

`py -3.13 orchestration/gate.py`: **FAIL, environment-only frontend toolchain
blocker**. Backend pytest passed (`1998 passed, 28 skipped`) and backend Ruff
passed. Frontend typecheck failed because TypeScript is not installed; frontend
test/build failed because `vitest` and `next` are not found. No frontend files
changed and no dependency installation was performed.

AutoLab: not applicable (diagnosis and bounded correctness repairs, not an
iterative metric optimization).

Bumblebee: not applicable (no manifest, lockfile, dependency loader, or image
changed).

No push. No deploy. Auditor: rerun the focused suites, full backend suite, and
deterministic gate from an environment with frontend dependencies installed.
