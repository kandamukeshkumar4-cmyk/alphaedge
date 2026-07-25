# STATE110 — First Real Artifact Pipeline

## Confirmed from scout (SCOUT110-ARTIFACTS.md)

**Artifact contract (`predictor._artifact_probability`):**
- Requires all three of `model_artifact_path`/`artifact_path`, `model_calibrator_path`/`calibrator_path`, and `feature_columns` (non-string Sequence).
- Model API: `joblib.load(...).predict_proba([row])[0][1]` (YES class index 1).
- Calibrator API: `joblib.load(...).predict([raw_probability])[0]`.
- Missing any of the three → `None` → implied passthrough. Partial set → `ValueError`.

**Dataset N (population A):**
- Prod scored LIVE forecasts: **206** (GET track-record / eval aggregates / model-ab, 2026-07-25).
- Category histogram: Culture 66, Sports 56, Crypto 46, FIFA WC2026 23, Tech 8, Economics 5, Politics 2.
- A/B-sanctioned lock-time features: `market_implied_probability`, `time_to_resolution_hours` (+ lock-time category encoding only).
- Consequence confirmed: `ForecastService.predict` previously passed no artifact paths → `PRODUCER_IMPLIED_PASSTHROUGH` for non-FIFA markets.

**Ship choice (scout §4):** calibrated logistic on population A, walk-forward via `build_v40_folds`, joblib + calibrator + **feature_columns sidecar**, wire active registry into predict, `activate=False` default, weekly retrain dual-wired. CLV gate untouched.

**Trainer location:** `backend/app/forecasting/generic_trainer.py` (prediction-facade package; shares constants with `generic_artifact.py`).

---

## Verbatim gates

### 1. loop110 tests

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop110_artifacts.py --basetemp=E:/polymarket-worktrees/loop110-artifacts/.pt
.........                                                                [100%]
9 passed in 11.06s
```

### 2. ruff

```text
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### 3. alembic heads

```text
$ cd backend && uv run alembic heads
066_alpha_validation (head)
```

(Zero migrations — registry already exists.)

### 4. openapi + authz

```text
$ cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py tests/test_loop26_authz_matrix.py --basetemp=E:/polymarket-worktrees/loop110-artifacts/.pt2
.....                                                                    [100%]
5 passed in 35.22s
```

### 5. full suite

```text
$ cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop110-artifacts/.ptf
2151 passed, 28 skipped in 473.36s (0:07:53)
```

---

## Local trainer run (fold Briers)

Synthetic N=24 seed rows (Sports/Culture, lock-time features + closing_implied). Artifact landed inactive.

```text
=== TRAINER METRICS TABLE ===
overall model_brier=0.09219800774811938
overall implied_passthrough_brier=0.25598684210526307
overall closing_line_brier=0.2864131578947368
fold_count=10 train_rows=24
fold | model_brier | implied_brier | closing_brier | n
   0 | 0.000000 | 0.266562 | 0.298212 | 2
   1 | 0.275464 | 0.182812 | 0.208462 | 2
   2 | 0.015892 | 0.289062 | 0.320712 | 2
   3 | 0.000000 | 0.275313 | 0.306963 | 2
   4 | 0.275452 | 0.266562 | 0.298212 | 2
   5 | 0.015376 | 0.182812 | 0.208462 | 2
   6 | 0.000000 | 0.289062 | 0.320712 | 2
   7 | 0.278318 | 0.275313 | 0.306963 | 2
   8 | 0.015379 | 0.266562 | 0.298212 | 2
   9 | 0.000000 | 0.275625 | 0.308025 | 1
artifact_dir= ..\.pt-trainer-run
feature_columns= ['market_implied_probability', 'time_to_resolution_hours', 'category__Culture', 'category__Sports']
activate= False
```

---

## What shipped

1. **Trainer** `app/forecasting/generic_trainer.py` — calibrated sklearn logistic, `build_v40_folds` embargo walk-forward, lock-time category one-hots (min-count drop, no padding), joblib model + calibrator + `feature_columns.json` sidecar, metrics include model / implied-passthrough / closing-line Brier per fold + overall.
2. **Loader** `app/forecasting/generic_artifact.py` — ACTIVE registry only when sidecar contract present.
3. **Wiring** — `ForecastService.predict` injects paths when features complete; missing feature → passthrough (never invent). `prediction_writer` + `forecast_autolock` load active artifact once per pass.
4. **Retrain** `app/workers/generic_artifact_retrain.py` — weekly dual-wired (wall-clock + ARQ Mon 04:30), single-flight, always `activate=False`.
5. **Tests** `tests/test_loop110_artifacts.py` — 8 required names + locktime loader kill-shot.

## AutoLab

AutoLab: baseline=passthrough producer for generic markets (scout-confirmed) | benchmark=tests/test_loop110_artifacts.py + walk-forward Brier vs implied/closing | iterations=1 (trainer+wiring+retrain green) | budget=1/mission | outcome=improved (artifact path wired; CLV display authority untouched)

## Extra scope noticed (not fixed)

- `prediction_writer` was missing from `_ALL_LOOPS` before this loop; added alongside `generic_artifact_retrain` for heartbeat visibility.
- Prod N=206 not exercised in CI (no prod DB); trainer proven on synthetic seed.
