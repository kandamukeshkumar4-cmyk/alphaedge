# Loop V51 state

## BLOCKED — historical model-type provenance (Q2)

As of 2026-07-16, repository history confirms that `ML_MODEL_TYPE` was added
with an `xgboost` default, and the live public endpoint confirms the current
default. Neither source proves that Railway never set an override during the
forecast accrual interval. `railway status` from this worktree reports no linked
project, so deployment/config history cannot be read here without an operator
link or a non-secret export.

V51 does not infer constancy. `run_forecast_score_ab` returns the structured
`model_type_history_unverified` refusal until both
`AB_MODEL_TYPE_HISTORY_VERIFIED=true` and a non-secret
`AB_MODEL_TYPE_HISTORY_EVIDENCE` reference are supplied from Railway history.
It records no Briers, delta, or winner in that state.

## Implemented

- C-1 population is `forecast_scores -> forecast_logs -> external_markets`; no
  paper-order or legacy snapshot-matrix row can enter the comparison.
- Pre-lock adapter is exactly `market_implied_probability` and
  `time_to_resolution_hours`, both persisted on the forecast lock. The result,
  `resolved_at`, and `scored_at` are not features.
- V40 folds use `resolved_at < T_eval_min` for training, `locked_at >=
  T_eval_min` for evaluation, and a named one-row resolution-time embargo.
- `ab_ready` reports the binding 100 correlation-cluster gate while retaining
  nominal forecast-score count and concentration disclosure.
- Public `GET /api/v1/system/model-ab` is cache-only. Controlled refreshes are
  persisted as `JobRun` records; the public GET never trains models.
- Railway's `backend/Dockerfile` installs the lock-pinned `ml-extra`; direct
  `uv` verification imported LightGBM 4.6.0. Docker Desktop was unavailable,
  so the unpushed image has not been built locally or verified in Railway.

## LOOP LOG

| date | status | evidence |
| --- | --- | --- |
| 2026-07-16 | PARTIAL / Q2 BLOCKED | Focused V51 tests passed (8); Ruff passed; `uv --extra ml-extra` imported LightGBM 4.6.0; Bumblebee project scan completed with 0 findings / 881 package records. Final `py -3.13 orchestration/gate.py` passed: backend 1704 passed / 28 skipped; frontend typecheck, 398 tests, and build passed. |
