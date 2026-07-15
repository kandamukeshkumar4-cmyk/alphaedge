# Loop V36 — Papercut backlog completion
> Runner: Cursor Grok 4.5 headless. Worktree E:/polymarket-worktrees/loop36-papercuts2,
> branch loop36/papercuts2.
## Tickets (fix(loop36): <ticket>)
- Q1 Read goals/loop-v35-papercuts/STATE.md — the sweep filed 13 papercuts;
  ~8 were fixed. Fix ALL remaining unfixed entries (frontend/src only),
  smallest-safe per cluster, evidence screenshot after each fix under
  goals/loop-v36-papercuts2/evidence/.
- Q2 Re-run the V35 sweep script (goals/loop-v35-papercuts/sweep.mjs) against
  the LOCAL stack post-fix; confirm each fixed item clean; file anything NEW
  found (fix if trivial, else document).
- Q3 Full frontend gates (counts) + FULL playwright + fresh verifier. STOP.
## Ownership: frontend/src/**, goals/loop-v36-papercuts2/**. Design rules
apply (text-bg on accent). Never backend/e2e-logic/deploy. Never push/merge.
