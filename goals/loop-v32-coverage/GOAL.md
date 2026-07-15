# Loop V32 — Backend test-coverage hardening (TESTS ONLY)

> Runner: ChatGPT/Codex IDE. Worktree E:/polymarket-worktrees/loop32-coverage,
> branch loop32/coverage. Constitution rules apply. Advisor gate: waived per
> the DIR-V29-001 precedent (orchestrator-reviewed lane).

## Mission
Measure real line/branch coverage of backend/app, then close the most
DANGEROUS gaps — money paths, auth paths, resolution/scoring paths — with
meaningful tests (assert behavior, not implementation). Coverage % is the
map, NOT the goal: no assert-free "coverage tests", no snapshotting
internals; every new test must be able to FAIL for a real bug.

## Ownership
YOURS: backend/tests/** (new files or additive cases), a coverage config
entry if needed (pyproject [tool.coverage] additive), goals/loop-v32-coverage/**.
FOREIGN: backend/app/** (defects found -> BUG REPORTS in STATE.md, never
fix), frontend/**, deploy configs, and DO NOT touch these test files owned
by active lanes: test_sports_results_connector.py (V31),
test_activity_trades.py / test_social.py (V30).

## Tickets (continuous; commit test(loop32): <ticket>)
- T1 Baseline: add pytest-cov as a dev dep ONLY if already absent from the
  uv dev extras (check first); run coverage over backend/app; commit the
  report summary (module -> line% table, worst 20) into STATE.md. No test
  changes yet.
- T2 Money paths: raise coverage of the lowest-covered modules among
  ledger/settlement/order_book/risk services with behavior tests (edge
  amounts, concurrent claims where harness allows, failure rollbacks).
- T3 Auth + resolution paths: same for auth/security modules and
  external_market/scoring/forecast services (leakage-gate edge cases:
  exactly-at-close locks, VOID resolutions, double-resolve idempotency).
- T4 Re-measure + report: before/after coverage table in STATE.md; full
  gate (counts!) + ruff + fresh verifier. Honest note on what remains
  uncovered and why (e.g. network clients mocked elsewhere). STOP.
