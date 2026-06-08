# Goals — Quant Engine execution queue

> **MULTI-SPORT (2026-06-06):** the app now covers **both NBA and FIFA World Cup
> 2026** as parallel sport tracks sharing one sport-agnostic forecast engine. The
> NBA Phase-3 work continues and merges; the [FIFA WC2026 track](phase-fifa-wc2026.md)
> is additive and must not regress NBA. Cross-track context:
> [`docs/handoff/CODEX-fifa-track.md`](../docs/handoff/CODEX-fifa-track.md).

This is the ordered work queue that turns [docs/project/QUANT_ROADMAP.md](../docs/project/QUANT_ROADMAP.md) into discrete units Codex can pick up one at a time. Each goal binds to a reusable procedure in [/workflows](../workflows).

## How to consume a goal (protocol)

1. Pick the goal whose **status is `ACTIVE`** (only one at a time; respect `depends_on`).
2. Open the goal file → run its bound **workflow** → satisfy its **acceptance gate**.
3. Apply the [Shared Definition of Done](../workflows/README.md#shared-definition-of-done-every-goal).
4. Update the **status** in the table below, record the **PR line**, then promote the next `QUEUED` goal to `ACTIVE`.

## Queue

| Phase | Goal | Status | Depends on | Workflow | Gate (one line) |
|---|---|---|---|---|---|
| 0 | Data + CLV backtester | ✅ DONE | — | backend-feature | connectors + snapshots + `clv.py`/`walk_forward.py` shipped with tests |
| 1 | [Signals: arbitrage + dutching](phase-1-signals.md) | ✅ DONE | 0 | backend-feature | net-of-fees arb/dutch, resolution-matched, mismatch excluded |
| 2 | [Smart-money tracker](phase-2-smart-money.md) | ✅ DONE | 0 | backend-feature | on-chain P&L matches reference wallet; no keys |
| 3 | [Forecast Engine v0 (NBA)](phase-3-forecast-engine.md) | ✅ DONE | 0 | backend-feature + **clv-model-gate** | executable-price CLV gate, real NBA features (Elo/rest/pace/rating), isotonic ECE calibration, CPCV + deflated-Sharpe; 224 tests pass |
| FIFA | [**FIFA World Cup 2026 track**](phase-fifa-wc2026.md) | ✅ DONE | 0 | backend-feature + **clv-model-gate** | FIFA markets catalog, dataset loaders (Tier 0), feature engineering (no-leakage), W/D/L ensemble + Poisson + 10k MC, wire-in to predictor; 237 tests pass |
| 4 | [LLM / NIM assist](phase-4-llm-nim.md) | ✅ DONE | 3, FIFA | backend-feature | provider swappable (OpenAI/NIM/Gemini); AST guard: LLM can't set stake/side/`is_edge`; 265 tests pass |
| 6 | [Overlay + CLV tracking](phase-6-overlay-tracking.md) | 🟢 ACTIVE | 1,2,3,4 | ui-feature | honest labels + live CLV track record; safety tests pass |
| 5 | Market making (optional) | 🅿️ DEFERRED | 0–3 proven | backend-feature | paper-only; opt-in before live capital |

Status legend: ✅ DONE · 🟢 ACTIVE · 🟢 ACTIVE ∥ (active, runs in parallel) · ⏳ QUEUED · 🅿️ DEFERRED · 🔴 BLOCKED.

## Rules that override speed

- Never weaken `PAPER_TRADING_ONLY`, the order path, or any deploy/safety gate to close a goal.
- A prediction that doesn't beat the closing line being **hidden** is a *correct* outcome, not a failure.
- Keep the repo green between goals: each goal starts from a passing baseline.
