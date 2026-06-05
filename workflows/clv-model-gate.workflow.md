# Workflow: clv-model-gate

For **any predictive model** (Phase 3 forecast engine and anything after it). This is the rule that separates a quant signal from a YouTube-bot guess. Runs *in addition to* `backend-feature`.

## The gate

> A model is `is_edge=true` **only if**, on out-of-sample walk-forward evaluation, its **CLV is positive** AND its **Brier score is lower than the closing line's** Brier on the same games. Otherwise the model is hidden — never shown as edge, never paper-staked.

## Steps

1. **Baseline = the market.** Compute the closing-line Brier/log-loss on the evaluation window using `backend/app/backtesting/clv.py`. This is the number to beat. Record it.
2. **No lookahead.** Build features (`backend/app/ml/features.py`) only from data available *before* event start. The leakage negative-control test must FAIL if any post-event field leaks in.
3. **Walk-forward only.** Evaluate with `backend/app/backtesting/walk_forward.py` (training window strictly before the evaluation window). No random k-fold on time series.
4. **Calibrate.** Apply isotonic/Platt calibration; emit a reliability curve and check it improves over raw probabilities.
5. **Apply the gate.** Set `is_edge` per the rule above via `backend/app/backtesting/significance.py` `assess_closing_edge`, so edge requires a minimum resolved sample AND a paired-bootstrap lower bound above zero — not a raw small-sample comparison. A synthetic model that does *not* beat the closing line MUST resolve to `is_edge=false` (assert this in tests).
6. **Improve via the AutoLab loop** (`AGENTS.md`): measure → edit → re-measure → fold in; explicit budget; track best-so-far; stop after `K=3` no-progress iterations; never hand off worse than baseline; never weaken a guardrail to win the metric.
7. **Report.** PR line must include out-of-sample **CLV** and **Brier vs closing line**, plus the AutoLab line.

## Done when
The gate is enforced in code + tests, the negative-control passes, calibration holds, and the PR reports CLV + Brier-vs-closing-line. A model that fails to beat the closing line is correctly hidden (that is a *valid, honest* outcome — not a failure to paper over).
