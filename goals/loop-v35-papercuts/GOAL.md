# Loop V35 — UX papercuts sweep
> Runner: Cursor Grok 4.5 headless. Worktree E:/polymarket-worktrees/loop35-papercuts,
> branch loop35/papercuts.
## Tickets (commit fix(loop35): <ticket>)
- U1 Sweep: browse prod READ-ONLY (https://alphaedge-frontend-three.vercel.app)
  via the local e2e browser harness across all main routes, both themes,
  desktop+375px. File a papercut list in STATE.md (visual glitches, spacing,
  truncation, inconsistent empty states, dead links) with screenshots. NO
  invented issues; each entry needs evidence.
- U2 Fix the top ~8 by user impact (frontend/src only), one commit per
  cluster; keep the design rules (frontend/.claude/CLAUDE.md; text-bg on
  accent).
- U3 Full frontend gates + FULL playwright suite green + verifier. STOP.
## Ownership: frontend/src/**, goals/loop-v35-papercuts/**. Never backend/
e2e-spec logic (may add screenshots only)/deploy configs.
