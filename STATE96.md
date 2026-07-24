# Loop V96 — Multi-Factor Alpha Model

## Graph and ownership

`factors.py` contains seven deterministic, pure factor nodes. Their real edge is
a normalized score plus lock-time provenance. `validator.py` is the independent
maker-checker node; it consumes historical factor observations only after the
fan-in barrier. `alpha_service.py` reduces the current factor vector and
validator outcomes into read-only research output. `api/v1/alpha.py` exposes
that output but is intentionally not registered in `main.py`; the merge
orchestrator owns that integration.

Rejected factors are never reclassified as edge: response state contains each
rejection and its machine-readable reason. This Phase 1 implementation is
read-only over existing resolved data, so it adds no migration and does not
persist mutable runtime state.

## A1 — factor library

Status: DONE

```text
$ git log -1 --oneline
c966dec feat(loop96): A1 — add pure alpha factor library

$ cd backend && uv run --extra dev pytest -q tests/test_alpha_factors.py --basetemp=E:/polymarket-worktrees/loop96-alpha/.pt
..                                                                       [100%]
2 passed in 46.60s

$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

## A2 — independent out-of-sample validator

Status: DONE

Implementation contract: validator input is the existing resolved LIVE
`forecast_scores` population from `load_forecast_score_rows`, retaining its
locked-at ordering and correlation-cluster assignment. It reads only the
matching immutable `ForecastLog` rows. Factor inputs come only from locked
forecast fields and `snapshot_metadata.alpha_features`; the closing benchmark is
only `snapshot_metadata.closing_implied_probability` and is never a factor
input. Missing provenance and missing closing lines are separate rejection
reasons; no data is backfilled or inferred.

Checkable rule: chronological 60/40 IS/OOS split with at least 20 observations
and 8 OOS rows; 10,000 fixed-seed cluster bootstraps must have a positive 5th
percentile Brier delta, Newey-West-style OOS t-stat must be at least 2.0,
factor OOS Brier must beat closing, and IS-to-OOS degradation may not exceed
30%. A failure reports one stable rejection reason in that order.

```text
$ cd backend && uv run --extra dev pytest -q tests/test_alpha_factors.py tests/test_alpha_validator.py --basetemp=E:/polymarket-worktrees/loop96-alpha/.pt
.....                                                                    [100%]
5 passed in 6.11s

$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```
