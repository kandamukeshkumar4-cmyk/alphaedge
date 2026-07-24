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

## A4 — public alpha routes

Status: DONE

`GET /api/v1/alpha/factors?market=<external-id>` performs exact external-id
lookup and returns HTTP 404 `market_not_found` when absent. `GET
/api/v1/alpha/report` returns a fresh global validation summary with every
rejected factor and reason. Both routes are public/read-only and explicitly
paper-only. They are tested through an isolated FastAPI application only:
`main.py` is intentionally unchanged, so merge-time registration and live-route
proof remain an orchestrator responsibility.

```text
$ cd backend && uv run --extra dev pytest -q tests/test_alpha_factors.py tests/test_alpha_validator.py tests/test_alpha_service.py tests/test_alpha_api.py --basetemp=E:/polymarket-worktrees/loop96-alpha/.pt
.........                                                                [100%]
9 passed in 16.34s

$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

## Phase 2 — intentionally not built

- Regime Auditor: segment validated resolved history by volume tier,
  time-to-close bucket, and category; reject factors whose OOS evidence is not
  robust across regimes.
- Portfolio Constructor: combine only independently validated factors into a
  research-only inverse-volatility weight vector. It must not construct an
  order, stake, side, or executable instruction.
- Risk Decomposer: test residual alpha of that research vector with an OOS
  t-stat above 2.5 before a daily signal can be emitted.
- Scheduler: persist a daily no-signal outcome with evidence as faithfully as a
  qualifying research result.

## Ticket commit ledger

```text
$ git log -1 --oneline  # A2
bda81b1 feat(loop96): A2 — validate factors out of sample

$ git log -1 --oneline  # A3
3d1c894 feat(loop96): A3 — orchestrate alpha factor validation

$ git log -1 --oneline  # A4
c33bdb2 feat(loop96): A4 — expose alpha research routes

$ git log -1 --oneline  # portability correction
f286575 fix(loop96): bind scored forecast UUIDs
```

## Final verification

Scoped alpha proof is green after the UUID portability correction:

```text
$ cd backend && uv run --extra dev pytest -q tests/test_alpha_factors.py tests/test_alpha_validator.py tests/test_alpha_service.py tests/test_alpha_api.py --basetemp=E:/polymarket-worktrees/loop96-alpha/.pt
..........                                                               [100%]
10 passed in 10.68s

$ cd backend && uv run --extra dev ruff check app tests
All checks passed!

$ cd backend && uv run --extra dev pytest -q tests/test_llm_provider.py::test_llm_cannot_set_stake_side_or_is_edge --basetemp=E:/polymarket-worktrees/loop96-alpha/.ptguard
.                                                                        [100%]
1 passed in 14.28s
```

Final status: IMPLEMENTATION COMPLETE, REPO GATE BLOCKED.

The required full suite and `py -3.13 orchestration/gate.py` both stop in
unrelated collection of `tests/test_loop26_authz_matrix.py`: its
`AUTH_CLASS` snapshot lacks 50 already-registered routes. The gate additionally
reports missing frontend dependencies (`tsc`, `vitest`, and `next`). No alpha
test is implicated. This charter forbids repairing those unrelated surfaces.

AutoLab: not applicable (bounded new Phase 1 feature; no pre-existing metric
artifact was being iteratively improved).

## A3 — read-only alpha service

Status: DONE

The service queries an exact `ExternalMarket.external_id` (the endpoint's
canonical `market` value), then uses its latest immutable locked forecast as
the `as_of` factor source. It does not claim current freshness, backfill any
feature, aggregate scores, construct weights, or emit a trade-like decision.
Unavailable current factors cannot become valid merely because their historic
validator passes. Phase 1 returns only per-factor research scores and rejection
reasons.

```text
$ cd backend && uv run --extra dev pytest -q tests/test_alpha_factors.py tests/test_alpha_validator.py tests/test_alpha_service.py --basetemp=E:/polymarket-worktrees/loop96-alpha/.pt
.......                                                                  [100%]
7 passed in 7.91s

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
