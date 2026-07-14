# AlphaEdge model methodology

> **Paper-simulation disclaimer.** Every probability, Brier score, CLV number,
> and “edge” signal on AlphaEdge is produced inside a **paper-trading
> research system**. There is no real-money execution. Models may be wrong,
> sparse, or provisional. `PAPER_TRADING_ONLY=true` is required at runtime.
> Nothing here is financial advice.

This document describes the **forecast / evaluation stack as implemented** in
`backend/app/ml/**`, `backend/app/forecasting/**`, `backend/app/backtesting/**`,
and related eval/observability modules. It does not invent benchmarks or claim
live production edge.

Related: [API reference](./api.md) · [User guide](./user-guide.md) ·
[Operations](./operations.md).

---

## 1. What the forecast engine is

| Component | Role | Primary code |
|-----------|------|----------------|
| Feature builder | Build pre-decision feature rows; audit timestamps | `app/ml/features.py` |
| Classifier registry | XGBoost default; optional LightGBM | `app/ml/model_registry.py` |
| Trainer + walk-forward | Fit, calibrate, out-of-sample evaluate | `app/ml/trainer.py` |
| Calibration | Platt / isotonic / identity selection; ECE/Brier | `app/ml/calibration.py` |
| Predictor | Calibrated paper forecast + closing-line gate | `app/forecasting/predictor.py` |
| CLV / closing eval | Model vs closing line | `app/backtesting/clv.py` |
| Significance | Bootstrap / sample gates | `app/backtesting/significance.py` |
| Phase-3 gate helpers | Block “edge” unless walk-forward proof | `app/backtesting/replay.py` |
| Drift | Rolling Brier vs baseline | `app/observability/drift.py` |
| A/B harness | LightGBM vs XGBoost readout only | `app/ml/ab_harness.py` |
| Version registry | Store model/feature version rows | `app/ml/versioning.py` |

Default deployed model type: **`ML_MODEL_TYPE=xgboost`**
(`Settings.ml_model_type`). LightGBM is optional; if requested but not
installed, `build_classifier` **falls back to XGBoost** with a warning.

FIFA WC2026 slugs (`wc2026-*`) may route to a dedicated FIFA predictor; other
markets use the general artifact / feature path (`predict_market`).

---

## 2. Training path (XGBoost + calibration)

### Simple split train (fixture path)

`train_xgboost_model(fixtures_dir, artifact_dir)`:

1. Build training dataset + feature columns.
2. Chronological ~70/30 train/eval split.
3. Fit classifier via `_fit_calibrated_model`.
4. Fit **best calibrator** on holdout (`fit_best_calibrator`: identity vs Platt vs
   isotonic, picked by validation score).
5. Report Brier on calibrated probs; persist model + calibrator artifacts
   (joblib).

### Walk-forward train (primary honest path)

`train_walk_forward_xgboost_model` /
`train_walk_forward_xgboost_from_feature_matrix`:

- Uses rolling-origin (and optional combinatorial purged) splits from
  `app/backtesting/walk_forward.py`.
- Parameters include `train_window_size`, `eval_window_size`, optional
  `embargo_size`, CLV min edge, significance alpha / bootstrap samples.
- Returns walk-forward metrics including **model Brier vs closing Brier**, log
  loss, CLV positivity, and walk-forward calibration report.
- A/B harness reuses this trainer once per model type when enough resolutions
  exist (`MIN_RESOLVED_FOR_AB = 100`).

Artifacts are registered optionally via `register_model_version` /
`register_feature_version` (lineage rows — not auto-promotion).

---

## 3. Walk-forward evaluation & CLV gate

Edge is **not** “model probability ≠ market price”. The codebase treats edge as
a multi-condition gate.

### Closing-line evaluation (`evaluate_forecasts_against_closing`)

A model “beats closing” when **both**:

- model Brier **&lt;** closing-line Brier, and  
- model log loss **&lt;** closing log loss  

(`ForecastEvaluation.model_beats_closing` in `backtesting/clv.py`).

### Predictor edge (`predict_market`)

When walk-forward comparisons are present, `is_edge` requires:

1. `evaluation.model_beats_closing`
2. `significance.significant_beats_closing` (sample + bootstrap gates)
3. `clv.clv_positive` on forecast trades
4. Executable price edge &gt; 0

Otherwise reason strings explain which gate failed (e.g. “closing-line edge
gate not met”). Forecasts may still return a calibrated probability; UI surfaces
often mark non-gated forecasts as **provisional**
(`ForecastService.predict` → `provisional=not clv_gate_passed`).

### Phase-3 blocked reasons (`_phase3_blocked_reasons`)

A walk-forward result is blocked as edge when any apply:

| Reason key | Meaning |
|------------|---------|
| `insufficient_resolved_sample` | Edge sample gate not met |
| `model_brier_not_better_than_closing` | Model Brier ≥ closing Brier |
| `model_log_loss_not_better_than_closing` | Model log loss ≥ closing |
| `clv_not_positive` | Mean CLV not positive |
| `closing_edge_not_significant` | Significance gate failed |
| `edge_gate_not_met` | Catch-all |

**Honest outcome:** a model that fails to beat the closing line is **hidden as
edge** — that is correct system behavior, not a documentation failure.

---

## 4. Scoring metrics: Brier & ECE

| Metric | Definition in code | Lower is better? |
|--------|--------------------|------------------|
| **Brier** | Mean `(p − y)²` for binary outcomes | Yes |
| **Calibration error** | Binned \|mean predicted − observed rate\| aggregate (`calibration_error`) | Yes |
| **ECE** | Expected calibration error over reliability bins (`expected_calibration_error`, default 10 bins in reports) | Yes |

`CalibrationReport` records raw vs calibrated Brier, calibration error, ECE,
reliability curve bins, method name, and whether calibration **improved**
scores.

Public aggregates:

- `GET /api/v1/eval/aggregates` — mean Brier, calibration error, market count  
- `GET /api/v1/eval/calibration` — bins  
- `GET /api/v1/calibration/latest` — latest calibration payload  
- `GET /api/v1/track-record` — Brier over time, calibration bins, CLV histogram from **real resolutions only** (`n=0` / `thin_data` when sparse)

Analyst claim track record (separate surface) grades brief claims with
no-lookahead horizon rules; provisional badges apply when samples are small.

---

## 5. Leakage gate (no post-close / post-game features)

Training features must be known **at or before** the decision time.

`assert_no_post_game_leakage` in `app/ml/features.py`:

- Requires columns `known_at` and `decision_ts` (configurable names).
- Raises `ValueError` if any feature has `known_at > decision_ts`
  (“post-game feature leakage …”).
- Feature matrix builders call this audit before returning rows.

FIFA feature code similarly rejects post-game leak prefixes
(`data/fifa/features.py` leakage checks).

**Implication:** you cannot train on final scores, post-resolution book state, or
other information that only exists after the forecast decision timestamp.

Forecast **locking** for LIVE mode is also pre-close only: locks rejected when
the external market is not `OPEN` (`ForecastService.lock_forecast`).

---

## 6. Drift detection

| Setting | Default | Purpose |
|---------|---------|---------|
| `DRIFT_ALARM_ENABLED` | **false** | Master switch for firing alerts |
| `DRIFT_ALARM_THRESHOLD` | **0.05** | Absolute Brier drift magnitude that counts as alarm |
| `DRIFT_ROLLING_WINDOW` | **30** | Recent graded claims in rolling window |

`app/observability/drift.py`:

- Rolling mean Brier from recent graded confidences/outcomes.
- Drift = `rolling_brier − baseline_brier` (positive = worse than baseline).
- Baseline: overall all-time analyst aggregate Brier when present; else
  **0.25** (naive 50/50 Brier).
- Alarm when `|drift| > threshold`.
- When the flag is **off**, compute still returns a result but **does not**
  instantiate alert dispatch (zero external calls).

API: **`GET /api/v1/admin/observability/drift`** (admin key). There is no
public `/api/v1/eval/drift`.

---

## 7. Retrain / A/B — flag-gated, never auto-activates

| Mechanism | What it does | What it does **not** do |
|-----------|--------------|-------------------------|
| Manual / scripted walk-forward train | Writes artifacts + metrics | Flip production default without config change |
| `BACKTEST_NIGHTLY_ENABLED` | Optional nightly replay job into `backtest_runs` (default **off**) | Change `ML_MODEL_TYPE` |
| `run_walk_forward_ab` / `GET /api/v1/system/model-ab` | Compares LightGBM vs XGBoost OOS Briers when `resolved_count ≥ 100` | Set `applied: true` or rewrite settings |
| `GET /api/v1/system/resolved-count` | Reports count vs threshold + `model_default` | Flip the default model |
| `register_model_version` | Stores lineage row | Auto-swap active serving artifact |

Hard guardrail (from `ab_harness` module docstring):

> this harness **NEVER flips the default model**. The deployed model stays
> whatever `ML_MODEL_TYPE` says … the readout merely reports both Briers so a
> **human** can decide later.

Operator activation path is intentional config/deploy change (set
`ML_MODEL_TYPE`, ship artifacts), not an automatic win from A/B.

---

## 8. Ensemble (related, not a silent model swap)

`ENSEMBLE_ENABLED` (default true) routes multi-LLM ensemble providers when keys
exist; with zero providers it degrades to the single-model baseline. Category
router config defaults keep categories on `"single"` until CLV gate passes
(`ENSEMBLE_ROUTER_CONFIG`). Ensemble does not bypass RiskService for agent
orders.

---

## 9. End-to-end lifecycle (research honesty)

```text
Features known at decision_ts
  → Train walk-forward (no leakage)
  → Calibrate probabilities
  → Evaluate vs closing line (Brier / log loss / CLV / significance)
  → Serve calibrated p; mark edge only if gates pass
  → Lock LIVE forecasts only while market OPEN
  → Resolve from venue / settlement data
  → Grade → track-record / calibration / drift inputs
  → Optional A/B readout (never auto-activate)
```

Sparse early history is expected: track-record `n` and provisional flags exist
so empty scoreboards are not padded with synthetic wins.

---

## 10. What we refuse to claim

- That any model has proven real-money profitability.
- That A/B “which_would_win” is applied in production without human config.
- That provisional or ungated forecasts are CLV-validated edge.
- That drift alarms fire when `DRIFT_ALARM_ENABLED` is false.
- Fabricated historical Brier series when `n=0`.

For operators wiring env flags, see [operations.md](./operations.md). For HTTP
eval endpoints, see [api.md](./api.md).
