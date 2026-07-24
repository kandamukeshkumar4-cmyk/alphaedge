# Loop V97 — Multi-Factor Alpha Model Phase 2

## Graph

`factors → validator → regime auditor → portfolio constructor → risk decomposer
→ alpha run persistence → stop check`. Each node consumes the prior node's
output; rejected factors stay as evidence. All outputs are paper-only research
artifacts and never construct an order.

## A5 — Regime auditor

Status: DONE

Segments the validator's immutable resolved population by observed volume tier,
hours-to-close, and category. A factor needs positive predictive statistics in
at least two regimes; otherwise it is rejected as
`only_one_predictive_regime`. Missing regime provenance is never inferred.

```text
$ git log -1 --oneline
2ff0c5d feat(loop97): A5 regime audit

$ cd backend && uv run --extra dev pytest -q <all test_alpha_ files> --basetemp=E:/polymarket-worktrees/loop97-alpha2/.pt
13 passed in 35.91s
```

## A6 — Research-only portfolio constructor

Status: DONE

Builds an inverse-volatility, common-OOS research weight vector only. The
module has no RiskService, OrderBookService, order, or LLM execution import;
its test asserts those execution paths remain absent.

```text
$ git log -1 --oneline
5e2fc78 feat(loop97): A6 construct research weights

$ cd backend && uv run --extra dev pytest -q <all test_alpha_ files> --basetemp=E:/polymarket-worktrees/loop97-alpha2/.pt
16 passed in 10.21s
```

## A7 — Out-of-sample risk decomposition

Status: DONE

Regresses the combined research-return series against surviving factor-return
series. The only positive conclusion is `residual_alpha_t_stat > 2.5`;
otherwise persisted output is `no signal (evidence)`. An exact
factor-explained vector is deliberately no-signal, including under
floating-point degenerate variance.

```text
$ git log -1 --oneline
b19b652 feat(loop97): A7 decompose residual alpha

$ cd backend && uv run --extra dev pytest -q <all test_alpha_ files> --basetemp=E:/polymarket-worktrees/loop97-alpha2/.pt
19 passed in 11.98s
```

## A8 — Daily orchestration, persistence, API, and scheduler

Status: DONE

`AlphaRunService` persists one idempotent paper-only run per UTC day,
including validator/regime/constructor/decomposition evidence and all factor
rejections. `GET /api/v1/alpha/runs` returns latest plus history; `GET
/api/v1/alpha/latest-signal` returns the latest checkable research result.
The wall-clock-aligned `_alpha_model_loop` boot-catches up before computing the
next 07:00 UTC run and mirrors the ARQ cron at the same hour. No router wiring
was changed in `main.py`.

```text
$ git log -1 --oneline
3136a9e feat(loop97): A8 persist daily alpha runs

$ cd backend && uv run --extra dev pytest -q <all test_alpha_ files> --basetemp=E:/polymarket-worktrees/loop97-alpha2/.pt
24 passed in 9.74s

$ cd backend && uv run --extra dev ruff check app tests
All checks passed!

$ cd backend && uv run --extra dev pytest -q tests/test_inprocess_scheduler.py tests/test_heartbeat_guards.py --basetemp=E:/polymarket-worktrees/loop97-alpha2/.ptg
8 passed in 11.84s

$ cd backend && uv run --extra dev pytest -q tests/test_llm_provider.py::test_llm_cannot_set_stake_side_or_is_edge --basetemp=E:/polymarket-worktrees/loop97-alpha2/.ptguard
1 passed in 12.28s
```

## Final proof and review

```text
$ cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop97-alpha2/.ptf
2074 passed, 28 skipped in 587.63s (0:09:47)

$ py -3.13 orchestration/gate.py
PASS backend pytest (2074 passed, 28 skipped)
PASS backend ruff
FAIL frontend typecheck, frontend test, frontend build
```

The gate failure is unrelated to this backend charter: the checkout has no
frontend TypeScript/Vitest/Next executables. No frontend manifest or lockfile
was changed, so installing dependencies is out of scope. `requesting-code-review`
is not available in this environment; manual review of `HEAD~4..HEAD` found
no scope leak into order execution, no LLM execution path, no new router
registration, and no migration branch. Bumblebee is not applicable: this work
does not modify a dependency manifest, lockfile, loader, or deploy image.

AutoLab: not applicable (bounded new Phase 2 feature; no pre-existing metric
artifact is being iteratively improved).
