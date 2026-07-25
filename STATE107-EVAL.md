# STATE107-EVAL — /eval/aggregates + /eval/calibration repointed to forecast_scores

Date: 2026-07-25
Worktree: `E:/polymarket-worktrees/loop107-eval` (branch `loop107-eval/node`)
Work order: `DIAGNOSIS107-EVAL.md` → "## Exact implementation plan for a JUNIOR engineer".
Method: executed the plan exactly (phases in order, exact file list, exact field names,
exact helper name, exact test names). Zero design decisions taken.

## What changed (Fix A — backend)

VERDICT (a) from the diagnosis is the root cause: `/eval/aggregates` and `/eval/calibration`
read the legacy `evaluations` table (empty in prod — nothing in the live resolve path writes
it), while `/calibration/latest` and `/track-record` read `forecast_scores` (204 LIVE graded
forecasts on prod). The fix points the two public readers at the SAME proven collector.

Files edited (exactly the plan's charter):
1. `backend/app/api/v1/eval_routes.py`
   - `get_aggregates`: now calls `_collect_calibration_data(db)` (imported from
     `app.api.v1.calibration`) and computes `mean_brier`/`calibration_error` via
     `brier_score`/`calibration_error` from `app.backtesting.metrics`. Empty real store →
     honest `{window_days:7, mean_brier:0.0, calibration_error:0.0, market_count:0}`.
     NO longer inserts an `EvalAggregate` row on every GET (read-only GET restored).
   - `calibration_curve`: now calls `_collect_calibration_data(db)` and bins the rows via the
     new pure helper `_forecast_calibration_bins(predictions, outcomes, n_bins=10)`.
     Bin shape `{bin,count,mean_pred,mean_outcome}` preserved for
     `frontend/src/lib/calibration-api.ts`.
   - `_forecast_calibration_bins`: added verbatim from the plan (pure, not bound to
     `Evaluation`).
   - Removed the now-unused `from app.eval.service import EvalService` import (ruff F401).
   - `GET /eval/evaluations` left untouched (honest legacy `Evaluation` list; plan's
     "Optional clarity" docstring tweak SKIPPED per session rule "where the plan says
     optionally, SKIP the option").
2. `backend/app/eval/service.py`
   - Added the plan's short docstring to `compute_aggregates`: "Legacy Evaluation table;
     public HTTP now uses forecast_scores." Method body unchanged (kept for the legacy unit
     test `test_compute_aggregates_uses_weighted_calibration_error`). `evaluate_market`,
     `run_eval_on_resolve_task`, `calibration_bins`, and the `Evaluation` model are untouched.
3. `backend/tests/test_eval_aggregates_forecast_scores.py` (NEW — plan A4 exact name)
   - `test_eval_aggregates_empty_when_no_forecast_scores`
   - `test_eval_aggregates_matches_calibration_latest_on_forecast_scores`
   - `test_eval_calibration_bins_count_sum_equals_scored_n`
   - Test 4 (`..._does_not_insert_eval_aggregate_row`) was marked "(optional but
     recommended)" in the plan → SKIPPED per the session rule. The no-insert behavior is
     nonetheless guaranteed structurally: the route no longer calls `compute_aggregates`
     (the only thing that did `session.add(EvalAggregate(...))`).
   - Fixture style mirrors `test_track_record_api.py` / `test_external_market_scoring.py`
     (Forecaster + ExternalMarket RESOLVED + ForecastLog LIVE + ForecastScore). Seeds are
     deterministic (explicit probabilities 0.2/0.8, explicit pre-close `locked_at`); no
     randomness, no fabricated production numbers.

`backend/tests/test_eval_service.py` — NOT edited. Plan A4 item 5 says KEEP
`test_compute_aggregates_uses_weighted_calibration_error` (it tests legacy `Evaluation` unit
math, not the HTTP contract); it still passes.

## Fix B — /ensemble/autolab (frontend-only honesty; CONFIRMED, no change)

- No backend route exists and none was invented (OpenAPI has zero ensemble paths; GET → 404).
- `frontend/src/app/eval/page.tsx:74-77` maps a non-OK (404) response to
  `outcome:"not_run"` (and catches network rejections the same way); lines 122-140 then render
  `data-testid="ensemble-not-measured"` ("Not yet measured", no fabricated bars). Confirmed by
  inspection. No existing component test covers this section (`feature-surfaces.test.tsx`
  covers a different market-surface ensemble badge), so the junior check was done by code
  inspection as the plan permits.
- Escalation check performed per the plan: grepped the backend for a real ensemble-vs-baseline
  Brier store. The only "ensemble" code is the flag-gated LLM `ensemble_forecast` runtime path
  in `app/api/v1/market_prediction.py` — NOT a persisted ensemble-vs-baseline Brier artifact.
  Nothing to escalate (matches the diagnosis: "Current openapi + grep: none").
- The plan's "Optional copy tweak" was SKIPPED per the session rule.
- No frontend source files were modified.

## NEEDS COORDINATION

1. **Test-file name: plan charter vs stop-condition gate.** The plan (A4) fixes the new test
   file as `backend/tests/test_eval_aggregates_forecast_scores.py` (created, 3 tests passing).
   The session STOP CONDITION, however, runs `pytest -q tests/test_eval_routes.py`, a file
   that does not exist in the repo and never has (verified: `git log -- tests/test_eval_routes.py`
   is empty; `ls` → "No such file or directory"). I followed the plan's exact file list (the
   auditor diffs edits against the plan's file charter; "extra scope is a defect"), so I did
   NOT create an out-of-charter `test_eval_routes.py`. The eval-route tests the gate intends to
   run live in `test_eval_aggregates_forecast_scores.py` and pass (see the A5 proof output
   below, which is the plan's own proof command). The orchestrator should reconcile the two
   names: either the gate path or the plan's file name.
2. **Commit scope.** The session template showed `feat(loop106):` / `fix(loop106):`, but this
   worktree/branch/STATE/DIAGNOSIS are all `loop107`. I used `feat(loop107):` to match the
   actual branch (`loop107-eval/node`) rather than mislabel the commit `loop106`.

## Environment note (not a code issue)

The `E:` drive was 100% full (322 MB free), so the first frontend `npm ci` / `npm install`
failed with `ENOSPC` and produced a corrupt `node_modules` (typecheck showed truncated
`framer-motion`/`@xyflow` `.d.ts` and missing `@astryxdesign/core/*`). I deleted the corrupt
`node_modules` (reclaimed `E:` to ~7.2 GB free) and re-ran `npm install` cleanly (647 packages,
no ENOSPC). Frontend gates below were run against the clean install. An empty staging dir
`F:\loop107-eval-node-modules` was created during an attempted junction workaround and could
not be removed (sandbox-protected path); it is empty and outside the worktree — harmless.

## STOP CONDITION — VERBATIM tool output

### 1. `cd backend && uv run --extra dev pytest -q tests/test_eval_routes.py --basetemp=E:/polymarket-worktrees/loop107-eval/.pt`

```
ERROR: file or directory not found: tests/test_eval_routes.py


no tests ran in 0.00s
```

(See NEEDS COORDINATION #1 — this gate path does not exist; the plan's charter names the file
`test_eval_aggregates_forecast_scores.py`, whose tests pass in the A5 proof below.)

### 2. `cd backend && uv run --extra dev ruff check app tests`

```
All checks passed!
```

### 3. `cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop107-eval/.pt2`

```
...                                                                      [100%]
3 passed in 16.31s
```

No regeneration needed: response field names are unchanged and the snapshot tracks
summary/tags/success-response only; function names (hence auto-summaries "Get Aggregates" /
"Calibration Curve") and tags were preserved. Added docstrings map to OpenAPI `description`,
which the snapshot does not compare.

### 4. `cd frontend && npm run typecheck`

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```
exit code 0 (no diagnostics).

### 5. `cd frontend && npm run lint`

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```
exit code 0 (no warnings; `--max-warnings=0` enforced).

### 6. `cd frontend && npm run build`

```
> alphaedge-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.18

   Creating an optimized production build ...
 ✓ Compiled successfully in 49s
```
```
○  (Static)   prerendered as static content
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand
```
exit code 0.

## Plan A5 proof commands (the plan's own local proof — VERBATIM)

`cd backend && uv run --extra dev pytest -q tests/test_eval_aggregates_forecast_scores.py tests/test_calibration.py tests/test_track_record_api.py tests/test_eval_service.py --basetemp=...`

```
..................                                                       [100%]
18 passed in 13.88s
```

New file alone:

```
...                                                                      [100%]
3 passed in 47.57s
```

`cd backend && uv run --extra dev ruff check app/api/v1/eval_routes.py app/eval/service.py tests/test_eval_aggregates_forecast_scores.py`

```
All checks passed!
```

## CLV law / guardrails honored

- No fabricated rows: `evaluations` was NOT backfilled; no `Evaluation` invented from
  forecasts. Empty real store → honest zeros / empty bins / `market_count:0` (made
  EXPLAINABLE via the `forecast_scores` source, not filled with dummy Brier).
- No weakened thresholds: `/calibration/latest` gate and `/track-record` math untouched
  (ground truth). BRIER gate unchanged.
- No migration / no Alembic / no backfill script (zero migrations).
- `ScoringService`, resolve workers, risk/order path, and `PAPER_TRADING_ONLY` untouched.
  `paper_trading_only` remains true.
- No fake `/ensemble/autolab` route returning fabricated `measured` Brier.
- No GET side-effect re-introduced: `/eval/aggregates` no longer inserts `eval_aggregates`.
- Did NOT "fix" by widening a non-existent window filter; the readers now point at the real
  store (`forecast_scores`) per VERDICT (a).
- No push, no deploy, no prod mutation (read-only only; no prod calls were even needed here).
- No secrets printed or set.

## AutoLab

AutoLab: not applicable (one-shot read-surface repoint; the plan's A5 test command is the
verification; no iterative metric loop was run).

## git log --oneline

```
17c1c59 feat(loop107): repoint /eval/aggregates + /eval/calibration to forecast_scores
67b380b docs(loop105): final prod smoke HEALTHY — wave 105 verified end to end
328afd8 merge(loop105): pagination-aware frontend — Load more + explicit limits (Cursor; Grok audit PASS, no blockers)
c497306 feat(loop105): record catalog UI gate proofs in STATE105-CATALOGUI
6182b15 docs(loop106): record gate output and handoff state in STATE106.md
c869d44 fix(loop106): point calibration bins at the real eval endpoint
```
