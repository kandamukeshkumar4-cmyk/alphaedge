# Parallel Loop Orchestration V2 — PM contract (2026-07-30)

Orchestrator: Claude (Fable 5, cloud session, PR #58 /
`claude/missing-edge-thread-yqbqoc`). Same "plan big, execute small" pattern
as V1 (`ORCHESTRATION.md`, now CLOSED): the orchestrator plans, monitors,
reviews, and merges; executors burn the tokens. Executors commit to their
own branch only; never push to others' branches, never merge, never rebase.

## The lanes (disjoint ownership — colliding = failed iteration)

| Lane | Executor | Branch | Owns | Assignment |
|------|----------|--------|------|------------|
| C: E2E repair | Claude (this session, subagents) | `claude/missing-edge-thread-yqbqoc` | `frontend/e2e/**` + components implicated by E1–E5 | `goals/loop-e2e-fix/STATE.md` |
| D: Backend bias-adjusted field | Codex or Grok (Cursor) | `loop-d-bias-adjusted` | `backend/**` only | `goals/loop-d-bias-adjusted/ASSIGNMENT.md` |
| E: A/B resolved-count watcher | Qwen (NIM) or Gemini | `loop-e-ab-watch` | `backend/app/ml/ab_harness.py` readout + admin surface only | `goals/loop-e-ab-watch/ASSIGNMENT.md` |

Non-collision rules carry over from V1: additive-only API changes documented
in `goals/loop-grok-backend/API-NOTES.md` conventions (new file per lane);
nobody touches `scripts/`, `orchestration/`, `.github/`, root configs, or
another lane's `goals/*` folder.

## Standing guardrails (non-negotiable, from AGENTS.md)

PAPER_TRADING_ONLY stays true. Order path untouched:
RiskService → OrderIntent → OrderBookService. No fabricated data or metrics;
honest empties; never weaken a test to pass. Gate before DONE:
backend `uv run --extra dev pytest -q` + ruff; frontend
typecheck/lint/vitest/build.

## Lane D brief — bias-adjusted probability API (unblocks P11)

P11 (favorite-longshot display layer) has been BLOCKED-ON-BACKEND since V1:
no API exposes a bias-adjusted probability. Ticket: expose the EXISTING
isotonic calibration (`backend/app/ml/calibration.py`, currently internal)
as an additive field on `/explain` (e.g. `calibrated_prob` beside
`model_prob`/`market_implied`), null when the calibrator has fewer than
BRIER_MIN_SAMPLE resolved outcomes (honest empty, never fabricated).
Fixture tests both states. Document the contract in
`goals/loop-d-bias-adjusted/API-NOTES.md`. One ticket, then STOP.

## Lane E brief — resolved-count watcher surfacing (P10 self-unblock)

P10 flips the default model only when resolved count ≥ 100, measured by
`python -m app.ml.ab_harness`. Ticket: surface that count on the existing
admin stats payload (additive field `resolved_outcomes_count`) so the
frontend can show progress toward the A/B gate. NEVER flip the default
model in this lane (test-enforced already — keep those tests intact).
One ticket, then STOP.

## Orchestrator duties (each check-in)

Same as V1: review each lane's new commits against guardrails, merge clean
work, leave the next directive in the lane's ASSIGNMENT.md, stop a lane on
scope-fence breach or 3 no-progress iterations.
