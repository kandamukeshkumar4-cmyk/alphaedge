---
id: phase-3-forecast-engine
phase: 3
status: QUEUED
depends_on: [phase-0]
workflow: backend-feature + clv-model-gate
full_spec: docs/project/QUANT_ROADMAP.md  (§3 Phase 3)
---

# Phase 3 — Forecast Engine v0 (the real quant prediction)

**Objective:** a calibrated gradient-boosted model (NBA first) that **replaces the hardcoded `implied + 0.03` stub** in `backend/app/agents/graph.py`. Gated on beating the closing line.

**Run the [clv-model-gate](../workflows/clv-model-gate.workflow.md) workflow** in addition to backend-feature — it is mandatory here.

## Scope / files
- `backend/app/ml/features.py` — real features: Elo, odds movement (open→current), implied prob, rest/travel/back-to-back, home/away, recent form, line-move velocity, injuries (field populated in Phase 4). Built from the snapshot store; assert no post-game leakage.
- `backend/app/ml/trainer.py` — rewrite: LightGBM/XGBoost on the real matrix with walk-forward CV. `backend/app/ml/calibration.py` — isotonic/Platt + reliability curve.
- `backend/app/forecasting/predictor.py` — serve calibrated prob + confidence; update `agents/graph.py` `prediction_node` to call it and **delete the `+0.03` logic**.
- `backend/app/risk/rules.py` — fractional Kelly stake suggestion with hard caps (paper only).

## Acceptance gate (the big one)
- Out-of-sample walk-forward **CLV positive** AND **Brier < closing-line Brier**.
- Edge is credited only when **statistically significant**: gate `is_edge` via `backend/app/backtesting/significance.py` `assess_closing_edge` (minimum resolved sample + paired-bootstrap lower bound > 0), never a raw small-sample comparison.
- A synthetic model that does NOT beat the closing line resolves to `is_edge=false` (asserted in tests).
- Feature no-leakage test passes; calibration improves reliability; Kelly caps respected.
- PR reports CLV + Brier-vs-closing-line + the AutoLab line.

## Safety
Paper suggestions only; no execution. LLM is not involved in the number.

## PR line
`Phase 3 forecast | gate=<met/blocked> | CLV=<+x.xx> Brier=<model vs closing> | verify=pytest <n> passed, ruff clean | safety=paper-only,no-exec: ok | review=<skill/manual> | AutoLab=baseline=<closing-line Brier> | benchmark=walk-forward CLV | iterations=<n+best> | budget=<used/limit> | outcome=<improved/stalled/retired>`

> Full paste-ready block: `docs/project/QUANT_ROADMAP.md` → §3 Phase 3.
