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
| 6 | [Overlay + CLV tracking](phase-6-overlay-tracking.md) | ✅ DONE | 1,2,3,4 | ui-feature | 4 panels (arb/dutch/smart/forecast) + CLV dashboard + paper P&L; disclaimer mandatory; 105 ext + fe typecheck + 4 be tests pass |
| X | [Mirror MVP close-out](loop-x-mirror-mvp.md) | ✅ DONE | 3, 6 | backend-feature + ui-feature | path scores + /mirror route + FanDuel deferred + safety tests; all gates green |
| Y | [True sell/close lifecycle](loop-y-sell-close.md) | ✅ DONE | X | backend-feature + ui-feature | sell/close endpoint + realized P&L + netted portfolio + no-double-pay settlement; all gates green |
| 5 | Market making (optional) | 🅿️ DEFERRED | 0–3 proven | backend-feature | paper-only; opt-in before live capital |

Status legend: ✅ DONE · 🟢 ACTIVE · 🟢 ACTIVE ∥ (active, runs in parallel) · ⏳ QUEUED · 🅿️ DEFERRED · 🔴 BLOCKED.

## Report coverage (technical-report gap trackers — 2026-07-07)

The gaps called out in the technical report are now implemented:

- **Streaming (Loop 2)** — implemented (SSE/token streaming through the agent
  graph; see loop2 commits).
- **Persistent memory (Loop 3)** — implemented (agent memory persisted across
  runs; `/api/v1/memories` surface).
- **Multi-model ensemble (Loop 4)** — implemented (ensemble across models;
  briefs expose `n_models`).
- **Market tool nodes (Loop 5)** — implemented (native market-data tool nodes in
  the agent graph; see `loop5` commit `5dc18b4`).

**Frozen by owner decision:** the Chrome extension track (`extension/`) is out of
scope and will not be developed, packaged, or documented further. See
[`REMAINING-OWNER-ACTIONS.md`](REMAINING-OWNER-ACTIONS.md).

## Next build loop (post E2E) — 2026-07-09

Quant phases and the E2E/UI/Ship/Opus loops are closed. The active improvement
queue is **[`build-loop-polish/STATE.md`](build-loop-polish/STATE.md)**
(P01–P12): surface what already shipped (search, Live badge, More nav,
screeners/dutching/weather on feed), dedupe `/markets` polls, Quest-theme
secondary pages, real calibration bins, arb honesty, then data-gated LightGBM
A/B. Runner: Grok 4.5 Cursor (or stronger). One ticket per iteration. Do not
greenfield — improve existing features. Owner blockers remain in
[`REMAINING-OWNER-ACTIONS.md`](REMAINING-OWNER-ACTIONS.md) (FIFA CSVs, ~100
resolves for model A/B, election dataset for instability).

## Rules that override speed

- Never weaken `PAPER_TRADING_ONLY`, the order path, or any deploy/safety gate to close a goal.
- A prediction that doesn't beat the closing line being **hidden** is a *correct* outcome, not a failure.
- Keep the repo green between goals: each goal starts from a passing baseline.
