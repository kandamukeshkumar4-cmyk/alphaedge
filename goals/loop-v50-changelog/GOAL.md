# Loop V50 — CHANGELOG + release notes (queued for OpenCode after V45)
> Runner: OpenCode CLI (model: GLM 5.2). Worktree
> E:/polymarket-worktrees/loop50-changelog, branch loop50/changelog. DOCS ONLY.
## Tickets (docs(loop50): <ticket>)
- C1 CHANGELOG.md at repo root: per-wave sections (waves 1-8) derived from
  the REAL git log (git log --oneline on loop3-agent-memory) + goals/*/
  STATE.md verdicts. Every entry cites its merge commit SHA. No invented
  features; user-facing wording.
- C2 docs/releases/wave-<n>.md: one page per wave — what shipped, why it
  matters to a user, notable fixes; same evidence rules.
- C3 Verification appendix in STATE.md: for 15 random entries, show the
  cited SHA exists (git show --stat). STOP.
## Ownership: CHANGELOG.md, docs/releases/**, goals/loop-v50-changelog/**.
NEVER app code; never secret values; never push/merge.
