# Loop V54 — QA sweep (TESTS ONLY)

> Runner: Cursor Grok 4.5. Worktree `E:/polymarket-worktrees/loop54-qa-sweep`,
> branch `loop54/qa-sweep`.

## Mission

Extend Playwright e2e coverage for locked-forecast panel, notification bell +
`/eval` loading states, and the V51 `resolved-count` API contract. Record a
CI-safe chromium suite run (skip visreg).

## Ownership (exclusive charter)

- WRITE: `frontend/e2e/**`, `goals/loop-v54-qa-sweep/**`
- READ: anything
- NEVER: modify app source, weaken existing tests, push, merge

## Tickets (one commit each: `test(loop54): <ticket>`)

| ID | Ticket |
|----|--------|
| Q1 | Playwright e2e for locked-forecast panel on market detail (locked `user_probability` + `locked_at`; provisional badge; graceful absent) |
| Q2 | Notification bell + `/eval` loading states against live-shape API mocks (match existing e2e patterns) |
| Q3 | API-contract: `GET /api/v1/system/resolved-count` asserts `correlation_clusters`, `ab_cluster_threshold`, `population.verdict` (+ types) via request pattern |
| Q4 | Run `npx playwright test` from `frontend/` CI-safe scope (`--project=chromium`, skip visreg); record counts in STATE.md |

## Gate

Done = Q1–Q4 DONE or BLOCKED in STATE.md. AutoLab: not applicable (QA coverage, no iterative measure).
