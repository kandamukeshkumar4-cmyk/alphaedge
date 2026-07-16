# Loop V45 — Documentation sync (waves 4-8 caught up)
> Runner: OpenCode CLI. Worktree E:/polymarket-worktrees/loop45-docsync,
> branch loop45/docsync. DOCS ONLY.
## Tickets (docs(loop45): <ticket>)
- W1 Diff docs/api.md against backend/tests/fixtures/openapi_snapshot.json
  (154+ paths): list missing surfaces (social, notifications, admin suite,
  eval/drift, system/sources, models) in STATE.md, then document each with
  auth requirements. Every claim verified against code (cite file).
- W2 User-guide additions: notification bell, trader profiles/following,
  /eval transparency page, the honest resolved-count source field.
- W3 Ops runbook additions: new loops (bridge, digest, retention, ops
  alerts, autolock funnel observability), visreg local workflow, CI
  workflows. Verify each name against app/api/v1/system.py _ALL_LOOPS.
## Ownership: docs/**, README touch-ups, goals/loop-v45-docsync/**. NEVER
app code. No secret values. Verifier: grep-verify every documented
endpoint/loop exists; list the verifications.
