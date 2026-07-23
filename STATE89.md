# Loop 89 — Accuracy Gate Diagnosis

## 1. VERDICT — healthy accrual, not a dead worker

**Verdict: (a) genuinely accruing and healthy.** The claim that the gate is
"just waiting" is materially correct, but its reported rate is stale: production
is at **93 / 100 correlation clusters** (seven short), not about 40/week.
The A/B remains intentionally blocked (`ab_ready=false`) because its
`forecast_scores` dataset has not reached the independent-cluster threshold;
there is no silent scheduler failure.

### Production proof — 2026-07-23

`GET https://alphaedge-api-production-b9db.up.railway.app/api/v1/system/resolved-count`
returned:

```json
{"paper_trading_only":true,"resolved_count":175,"forecast_scored_count":175,"correlation_clusters":93,"ab_threshold":100,"ab_ready":false,"dataset_source":"forecast_scores","valid_for_ab":true,"provenance_eligible_count":143,"model_types":"implied_passthrough"}
```

`GET /api/v1/system/loops` returned live in-process heartbeats (Railway runs
uvicorn, not ARQ):

```json
{"name":"external_resolve","planned":false,"running":true,"status":"ok","last_heartbeat":"2026-07-23T19:03:29.739960Z","interval_sec":900}
{"name":"external_market_bridge","planned":false,"running":true,"status":"ok","last_heartbeat":"2026-07-23T19:03:31.389024Z","interval_sec":900,"detail":"candidates=25 bridged=0 skipped=25 errors=0"}
{"name":"forecast_autolock","planned":false,"running":true,"status":"ok","last_heartbeat":"2026-07-23T19:03:31.094180Z","interval_sec":900,"detail":"external=827 open=642 pre_close=637 in_horizon=18 eligible=4 selectable=4"}
```

The `planned=false` field is only the data-stream plan; `running=true` plus the
fresh heartbeat is the scheduler truth. Safe-filtered Railway runtime logs had
no matching resolver heartbeat lines, so the public heartbeat endpoint is the
durable per-pass proof. `railway variables --json` revealed only the expected
`PAPER_TRADING_ONLY` and `REDIS_URL` scheduler-related names; no values were
printed.

Public resolved history shows active scoring through today: 8/24/13/26/49/28/17/10
resolved markets from July 16 through July 23. Reapplying the repository's
correlation normalization to those 175 public rows yields cumulative clusters
3/8/13/28/69/78/87/**93** by day. This is ~93 clusters across about seven days
(~93/week observed average), so a linear ETA for seven remaining clusters is
about **13 hours**. That is an estimate, not a promise; clustering and real
market settlement are lumpy.

Pipeline traced: `forecast_autolock` locks LIVE forecasts ->
`external_resolve` calls `resolve_external_markets` -> `ScoringService` creates
`ForecastScore` subject to the pre-resolution leakage gate ->
`load_forecast_score_rows` derives `correlation_cluster(external_id)` ->
`MIN_CORRELATION_CLUSTERS_FOR_AB=100` gates the controlled A/B readout. No
change is needed for that pipeline.

Calibration corroboration: `GET /api/v1/calibration/latest` returned
`markets_evaluated=175`, `brier_score=0.06658161325714286`,
`calibration_error=0.1958615352532019`, `gate=pass`, and
`paper_trading_only=true`.

## 2. Secondary fix — Scanner Studio compile timeout

Production QA found a real availability defect: `POST /api/v1/scanners/compile`
with a normal residual-language request waited 45 seconds and returned no bytes,
whereas a deterministic-only request (`sports model edge`) returned HTTP 200
immediately. Cause: the optional LLM assist had no timeout.

Commit: `db150e2 fix(loop89): bound scanner planner fallback`

- Added a 10-second bound around the optional LLM completion.
- A timeout falls through the existing exception path to the deterministic,
  validated, non-persisting scanner spec.
- Added a regression test for a slow completion. No order, risk, or paper-only
  code changed.

Proof:

```text
cd backend && uv run --extra dev pytest -q tests/test_scanner_llm_planner.py tests/test_scanners_api.py --basetemp=E:/polymarket-worktrees/loop89-sol/.pt
........                                                                 [100%]
8 passed in 39.56s

cd backend && uv run --extra dev ruff check app tests
All checks passed!

cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop89-sol/.ptf
1997 passed, 28 skipped in 344.11s (0:05:44)
```

## 3. Production QA sweep

No 5xx or paper-trading leak was found on health, signals/feed, briefs, skills,
scanners list, screener, or usage. Compact live results: health `ok` with
`env_guard=ok`; signals feed 6 with disclaimer; briefs total 113; skills 6;
public scanners 1; screener total 1540; usage seven-day totals sessions 0,
briefs 44. The LLM-assisted scanner compile timeout above is the one failure
found; the fix is local and requires orchestrator deployment.

Out of scope / not fixed: the sampled brief list contained an older null
`model_version`; historical backfill remains a separately scoped migration/data
task.

## 4. Final gate and worktree boundary

`py -3.13 orchestration/gate.py` ran backend pytest (**1998 passed, 28 skipped
in 386.32s**) and Ruff (**PASS**) but finished **FAIL** because this worktree
lacks frontend dependencies: TypeScript reported no local compiler, and
`vitest`/`next` were not recognized. Frontend files were untouched; no manifest
or lockfile was changed. This is an environment gate blocker, not a green gate.

Manual scoped diff review of `db150e2`: PASS — one timeout boundary, existing
fallback path, and a direct slow-provider regression test; no scope creep or
guardrail change. `requesting-code-review` is unavailable in this checkout, so
this manual review is the required fallback.

AutoLab: not applicable (production diagnosis plus one-shot availability fix,
not an iterative metric optimization). Bumblebee: not applicable (no package
manifest, lockfile, dependency loader, or deployment image changed).
