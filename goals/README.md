# Goals — Quant Engine execution queue

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
| 1 | [Signals: arbitrage + dutching](phase-1-signals.md) | 🟢 ACTIVE | 0 | backend-feature | net-of-fees arb/dutch, resolution-matched, mismatch excluded |
| 2 | [Smart-money tracker](phase-2-smart-money.md) | ⏳ QUEUED | 0 | backend-feature | on-chain P&L matches reference wallet; no keys |
| 3 | [Forecast Engine v0](phase-3-forecast-engine.md) | ⏳ QUEUED | 0 | backend-feature + **clv-model-gate** | positive CLV AND Brier < closing line, else hidden |
| 4 | [LLM / NIM assist](phase-4-llm-nim.md) | ⏳ QUEUED | 3 | backend-feature | provider swappable; LLM can't set stake/side/`is_edge` |
| 6 | [Overlay + CLV tracking](phase-6-overlay-tracking.md) | ⏳ QUEUED | 1,2,3,4 | ui-feature | honest labels + live CLV track record; safety tests pass |
| 5 | Market making (optional) | 🅿️ DEFERRED | 0–3 proven | backend-feature | paper-only; opt-in before live capital |

Status legend: ✅ DONE · 🟢 ACTIVE · ⏳ QUEUED · 🅿️ DEFERRED · 🔴 BLOCKED.

## Rules that override speed

- Never weaken `PAPER_TRADING_ONLY`, the order path, or any deploy/safety gate to close a goal.
- A prediction that doesn't beat the closing line being **hidden** is a *correct* outcome, not a failure.
- Keep the repo green between goals: each goal starts from a passing baseline.
