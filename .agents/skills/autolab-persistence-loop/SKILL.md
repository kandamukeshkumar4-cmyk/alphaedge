---
name: autolab-persistence-loop
description: Use for any AlphaEdge ticket whose job is to improve a working artifact — backtest accuracy, Brier/calibration scores, deploy smoke-test resilience, risk-unit coverage, API latency, or UX. Adapts the AutoLab long-horizon persistence finding (benchmark, edit, fold in empirical feedback under a wall-clock budget, starting from a correct-but-suboptimal baseline) onto AlphaEdge's Execution Gates and verificationCommands.
---

# AutoLab Persistence Loop — AlphaEdge

AutoLab benchmarks long-horizon agents on tasks that each start from a correct
but deliberately suboptimal baseline. Across frontier models the dominant
predictor of success was **not** first-attempt quality — it was persistence:
repeatedly benchmarking, editing, and folding in empirical feedback under a
strict wall-clock budget. Most models quit early or burned the budget making
almost no progress; models that sustained the loop (Claude Opus class among
them) kept improving the artifact for hours.

This skill turns that finding into a per-ticket discipline for AlphaEdge. The
benchmark is the repo's own measurement surface — `verificationCommands` in
`local.config.json`, the Execution Gates in `AGENTS.md`, and metric APIs
(Brier, calibration, latency, deploy smoke pass-rate).

Source bookmark: arXiv `2606.05080`, project site `https://autolab.moe/`, code
`https://github.com/autolabhq/autolab`, leaderboard
`https://autolab.moe/#leaderboard`. As of 2026-06-05, the paper abstract reports
17 evaluated models across 36 tasks, while public-site copy is inconsistent
between 7+ and 11+ model signals across 23 tasks; Claude Opus 4.6 is the
clearest strong signal for sustained long-horizon optimization. Verify the live
leaderboard before making model-selection claims.

## When To Use

Use it on any "make this working thing better" ticket: model accuracy,
Brier/calibration, backtest results, deploy resilience, risk-unit coverage, API
latency, or UX. Skip it (and say so in the PR) only when the fix is a one-shot
change with no measurable axis to improve.

## The Loop

1. **Start from a green baseline gate.** Begin from a passing Execution Gate and
   green `verificationCommands`. Correctness is never traded for a metric.
2. **Define the benchmark first.** Pick the measure: a `verificationCommands`
   pass/fail, a Brier/calibration score, a latency number, or a deploy smoke
   pass-rate. Record the baseline measurement.
3. **Iterate.** measure → edit → re-measure → fold the result into the next
   edit. Each edit is informed by the last measurement, not speculation.
4. **Persist to the budget.** Set an explicit budget at ticket start (iteration
   count or wall-clock). Do not stop after the first attempt.
5. **Do not thrash.** Track best-so-far. If `K` consecutive iterations show no
   measurable improvement (default `K=3`), stop: reorganize the approach or
   retire the direction with a reopen condition.
6. **Keep the best measured artifact.** Champion = best verified measurement.
   Never hand off worse than baseline.

## Two Failure Modes To Avoid

- **Quitting early** — handing off after one attempt with budget unspent.
- **Budget burn** — spending the budget with no measured progress and no
  stagnation call.

## Guardrails

- Never game the benchmark. A metric win that regresses a gate or guardrail is a
  dead end, not progress.
- Never weaken `PAPER_TRADING_ONLY`, the `RiskService → OrderIntent →
  OrderBookService` order path, or any deploy gate to hit a metric.

## Handoff Line

```text
AutoLab: baseline=<verified gate/measure> | benchmark=<metric/command> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
```

The line must include all five fields: baseline, benchmark, iterations/best
result, budget, and outcome.

See `AGENTS.md` → "AutoLab Persistence Loop" for the governing rule and
`local.config.json` → `autoLabPersistence` for the machine-readable config.
