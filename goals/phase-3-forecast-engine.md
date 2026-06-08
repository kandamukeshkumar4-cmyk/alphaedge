---
id: phase-3-forecast-engine
phase: 3
status: DONE
runs_parallel_with: phase-fifa-wc2026
depends_on: [phase-0]
workflow: backend-feature + clv-model-gate
full_spec: docs/project/QUANT_ROADMAP.md  (§3 Phase 3)
---

# Phase 3 — Forecast Engine v0 (the real quant prediction)

> 🔀 **Runs in PARALLEL with the [FIFA World Cup 2026 track](phase-fifa-wc2026.md) (2026-06-06).**
> The app supports **both NBA and FIFA** markets. The forecast **harness** built
> here (walk-forward CV, calibration, CLV-vs-closing gate, significance, Kelly,
> snapshot capture) is **sport-agnostic and shared** by the FIFA track — finish and
> merge this NBA work; FIFA is additive and must not regress it. Cross-track context:
> [`docs/handoff/CODEX-fifa-track.md`](../docs/handoff/CODEX-fifa-track.md).

> **Codex: read [`docs/handoff/CODEX-phase3-briefing.md`](../docs/handoff/CODEX-phase3-briefing.md) first.** Much of the original directive is already implemented (predictor wired, `+0.03` stub gone, 6 test files exist). The briefing lists the four gaps that actually remain, in build order.

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

## PR line (filled)

```
Phase 3 forecast | gate=blocked (is_edge=false — correct, no live closing-line data yet)
| CLV=gated | Brier=model vs closing (walk-forward CPCV, deflated-Sharpe reported)
| verify=pytest 224 passed, ruff clean
| safety=paper-only,no-exec: ok
| review=manual
| AutoLab: not applicable (deterministic gate — is_edge is the correct false negative)
```

> Full paste-ready block: `docs/project/QUANT_ROADMAP.md` → §3 Phase 3.
