# Loop V16 — Data Freshness & Liveliness (STATE)

Read GOAL.md first. One ticket per iteration. Update EVERY iteration.
Runner: ChatGPT/Codex IDE (local) · worktree E:/polymarket-worktrees/loop16-fresh · branch loop16/freshness.
Orchestrator (Claude main thread) reviews every commit; never push/merge/deploy from here.

## MIGRATION CLAIMS (041+; check loop-v15 STATE.md claims too — 038/039/040 landed)

| Number | Claimed by | Ticket | Status |
|---|---|---|---|
| (none) | | | |

## SHARED FILE CLAIMS (routes.py / ws.py / db/models.py / schemas/** / workers/tasks.py)

| File | Ticket | Status |
|---|---|---|
| `backend/app/api/v1/routes.py` | V1 | RELEASED 2026-07-13T21:17:44-04:00 |

## Tickets

| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| V1 | Trending ranks by recent activity; decided markets out | DONE | Additive `sort=active` ranks open/non-decided markets by 24h price movement, latest recent snapshot, close proximity, sync time, then lifetime volume; Discover, `/markets`, and `/home` consume that order without client-side volume re-sorting. Resolved markets remain reachable through a labeled Longshots / Decided affordance. Full proof and verifier output are in the loop log below. |
| V2 | Live Signals rail: named, valued, deduped | IN-PROGRESS | AutoLab budget: 3 measure/edit cycles; diagnosis pending. |
| V3 | Ticker freshness: DESC order, dedupe, age, 48h window | TODO | |
| V4 | F04 forecast auto-lock worker (unblocks grading) | TODO | new workers/forecast_autolock.py; claim tasks.py |
| V5 | Decided/closed market hygiene (no false LIVE chip) | TODO | |
| V6 | [LIVE] end-user re-test proof | TODO | prod READ-ONLY + local stack |

## LOOP LOG (append one entry per iteration; paste gate output tails)

### 2026-07-13 · V1 · DONE

Diagnosis: production default `/api/v1/markets` ranked by lifetime volume, and the frontend re-sorted the response by lifetime volume again. Captured 2026-07-14T00:57:20.9340164Z; the eliminated World Cup teams are honest resolved data, but wrong for Trending.

```json
{
  "before_default_top6": [
    ["pm-will-egypt-win-the-2026-fifa-world-cup", "resolved", 0.0],
    ["pm-will-morocco-win-the-2026-fifa-world-cup-464", "resolved", 0.0],
    ["pm-will-usa-win-the-2026-fifa-world-cup-467", "resolved", 0.0],
    ["pm-will-norway-win-the-2026-fifa-world-cup-893", "resolved", 0.0],
    ["pm-will-argentina-win-the-2026-fifa-world-cup-245", "open", 0.1745],
    ["pm-will-belgium-win-the-2026-fifa-world-cup-358", "resolved", 0.0]
  ],
  "after_policy_projection_top6": [
    ["pm-elon-musk-of-tweets-july-7-july-14-180-199", "open", 0.5255],
    ["pm-elon-musk-of-tweets-july-7-july-14-220-239", "open", 0.0375],
    ["pm-bitcoin-above-60k-on-july-14-2026", "open", 0.982],
    ["pm-bitcoin-above-64k-on-july-14-2026", "open", 0.048],
    ["pm-fifwc-fra-esp-2026-07-14-fra", "open", 0.4037],
    ["pm-fifwc-fra-esp-2026-07-14-esp", "open", 0.2988]
  ]
}
```

Task gate: backend `1416 passed, 28 skipped in 347.86s`; Ruff `All checks passed!`; frontend typecheck and lint passed; Vitest `56 passed (56)`, `344 passed (344)`; Next build compiled and generated 100/100 pages.

```text
=== GATE: backend pytest ===
1416 passed, 28 skipped in 447.40s (0:07:27)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
Test Files  56 passed (56)
Tests  344 passed (344)
PASS frontend test (exit 0)

=== GATE: frontend build ===
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

Fresh-context verifier: PASS — 9 focused backend tests, full backend Ruff, frontend typecheck, 7 focused frontend tests, and `git diff --check` all passed. The Windows pytest temp-cleanup warning occurred after gate exit 0 and is non-blocking.

Manual code-review fallback used because the Superpowers `requesting-code-review` skill is unavailable; the complete diff and every changed line were reviewed, and formatter-only churn in shared `routes.py` was removed before gating. `gh-address-comments`: not applicable (no PR/merge). Bumblebee: not applicable (no manifest, lockfile, dependency loader, or deployment-image change; no merge requested).

AutoLab: baseline=backend 1415 passed/28 skipped and frontend 55 files/341 tests green; prod top six had five resolved 0% rows | benchmark=active-sort focused tests plus full ticket/repo gates | iterations=1, best=backend 1416 passed/28 skipped and frontend 56 files/344 tests | budget=1/3 | outcome=improved

### ORCHESTRATOR REVIEW · V1 · bdcc4a9 · verdict: PASS
Exemplary diagnosis — the double volume-sort (backend default + frontend
re-sort) was the true root cause and the fix is additive on both sides.
Evidence quality is the bar for all remaining tickets. Continue V2 (find WHY
five identical price_jump rows exist before touching rendering — suspect the
same event re-emitted by the diff engine or one row rendered per snapshot).
Reminder for V4: claim workers/tasks.py in SHARED FILE CLAIMS before the
append; migration only if genuinely needed (claim 041). Orchestrator reviews
every commit here in STATE.md; a NEEDS-FIX verdict must be fixed before the
next ticket.
