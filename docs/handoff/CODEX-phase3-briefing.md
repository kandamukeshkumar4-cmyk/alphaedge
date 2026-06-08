# Codex Briefing — Context Update + Phase 3 Build Target

> Created: 2026-06-05. Read this before starting Phase 3 work.
> Purpose: (1) what changed in the repos, (2) the corrected, de-duplicated Phase 3 scope.

---

## Part 1 — What changed (governance, additive)

A new workflow doctrine — the **AutoLab Persistence Loop** — was wired into both
PawVital and AlphaEdge. It is **additive** to the existing gates (thermo-review,
AutoScientists, SIA). Nothing was removed.

AlphaEdge (`E:\polymarket clone`) surfaces:

- `AGENTS.md` → "AutoLab Persistence Loop" (governing rule for this repo)
- `CLAUDE.md`, `.cursor/rules/alphaedge-rules.md` → matching sections
- `.agents/skills/autolab-persistence-loop/SKILL.md` → tailored skill (benchmark =
  `verificationCommands` / Execution Gates / Brier-calibration)
- `local.config.json` → new `autoLabPersistence` block

PawVital workspace (`G:\MY Website`), for cross-reference:

- `RULES.md` (source of truth), `CLAUDE.md`, `AGENTS.md`,
  `.cursor/rules/shared-rules.md`, the skill, and
  `.agents/autoscientists/local.config.json` (now version 4) +
  `start-ticket.mjs` scaffold all carry the same loop.

### What this means for you on every improvement ticket

- Start from a **green baseline**; never trade correctness for a metric.
- Define the **benchmark first** (`verificationCommands` or a metric API); record
  the baseline measurement.
- Iterate **measure → edit → re-measure → fold in feedback** under an explicit
  budget. Do not stop after the first attempt.
- Track best-so-far; after **K=3** consecutive no-progress iterations, stop and
  reorganize or retire the direction.
- Emit this handoff line:

  ```text
  AutoLab: baseline=<verified start> | benchmark=<metric/gate> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
  ```

- Source bookmark (verify before any model-selection claim): arXiv `2606.05080`,
  `https://autolab.moe/` (leaderboard). Site copy is inconsistent on model/task
  counts; check the live leaderboard.

---

## Part 2 — What to develop next: Phase 3 Forecast Engine (CORRECTED scope)

**The "Phase 3 Forecast Engine Research Brief" / paste-ready directive is
partially stale. Do NOT execute it verbatim.** A code review (2026-06-05) found
much of it already implemented.

### Already DONE — do not redo

- `backend/app/agents/graph.py:77` — `prediction_node` already calls
  `predict_market()`. **There is no `+0.03` stub to delete; it is already gone.**
- `backend/app/forecasting/predictor.py` — already gates `is_edge` on
  `model_beats_closing AND significance.significant_beats_closing AND clv_positive`.
- `backend/app/ml/trainer.py` — walk-forward (`rolling_origin_splits`), XGBoost,
  `is_edge` gate, Platt calibration fit on train fold only.
- `backend/app/backtesting/significance.py` — paired-bootstrap lower bound > 0 +
  `min_sample` (`assess_closing_edge`).
- `backend/app/risk/rules.py` — fractional Kelly with caps, `paper_trading_only`.
- `backend/app/ml/calibration.py` — Platt + reliability curve.
- Tests already exist: `test_forecast_predictor`, `test_ml_calibration`,
  `test_ml_walk_forward_trainer`, `test_backtesting_significance`,
  `test_backtesting_clv`, `test_backtesting_walk_forward`. Add only the *missing*
  assertions below — do not re-create these files.

### The FOUR things actually missing — one reviewable branch each, in order

**1. Executable price + CLV convention (highest value, smallest) — phantom-edge bug.**
`predictor.py:81` and `risk/rules.py` compute edge against `implied_yes`
(midpoint), not the executable ask. A positive "edge" shown at midpoint can be an
artifact while real fills happen at the worse side.

- Edge/CLV must use `executable_yes_ask`; for the NO side use
  `executable_no_ask` and `closing_no = 1 - closing_yes`. Convert Kalshi no-bids
  into opposite-side asks when deriving executable prices.
- CLV evaluated on the **same side** as the recommendation, entry at executable
  price.
- Add tests: edge uses executable price not midpoint; no-side price conversion is
  correct.

**2. Real non-market features (the core of Phase 3).**
`features.py` is market-only (`implied_yes`, `opening_implied_yes`,
`odds_movement`, `line_move_velocity`, `snapshot_count`). A model fed only the
market's own price cannot honestly beat the closing line — the current
`is_edge=false` is the **truthful** state, not a bug.

- Add pregame-only signal: Elo, rest days, back-to-back, home/away, recent form,
  pace / offensive rating / defensive rating (RAPM / possession-level if data
  allows).
- Every feature `known_at <= decision_ts`.
- Add an explicit `assert_no_post_game_leakage(df)`. Closing price stays
  label/evaluation only — never a model feature.

**3. Isotonic calibration + ECE.**
Only Platt exists today. Add isotonic; choose the method on the **validation fold
only** (never on test); emit rolling Expected-Calibration-Error. Keep the
reliability curve.

**4. (Should, not blocking) CV hardening.**
Add CPCV (purge/embargo) + Deflated-Sharpe. Plain walk-forward is defensible for
v0 game-level data; treat this as a hardening pass, not a blocker.

**Also:** add a Power-method de-vig helper for two-sided quotes. Today
`implied_no = 1 - implied_yes`, which ignores the vig entirely.

### Deferred — do NOT pull into Phase 3

L2 order-book / OBI / micro-price (Phase 4), Dixon-Coles score-distribution model
(Phase 5), any `poly-maker` live execution. Paper-only; the LLM never produces
the number.

### Honesty / Goodhart guard

Until item 2 lands, the truthful Phase 3 result is `gate=blocked` /
`is_edge=false`. Do **not** tune thresholds, min-sample, or fixtures to force
`gate=met` — that violates the AutoLab/SIA Goodhart guard. A benchmark win that
regresses a holdout, a leakage test, or the synthetic-no-edge test is a dead end,
not a champion.

### Required PR line (from `goals/phase-3-forecast-engine.md`)

```text
Phase 3 forecast | gate=<met/blocked> | CLV=<+x.xx> Brier=<model vs closing> | verify=pytest <n> passed, ruff clean | safety=paper-only,no-exec: ok | review=<skill/manual> | AutoLab=baseline=<closing-line Brier> | benchmark=walk-forward CLV | iterations=<n+best> | budget=<used/limit> | outcome=<improved/stalled/retired>
```

Run workflows: `backend-feature` + `clv-model-gate` (mandatory here). Read
`docs/project/QUANT_ROADMAP.md` §3 as the spec, but treat its `+0.03` /
predictor-wiring items as already done.
