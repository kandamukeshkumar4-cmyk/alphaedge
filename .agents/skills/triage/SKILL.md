---
name: triage
description: Morning triage skill. Reads goals/README.md, recent git log, and last pytest output. Writes a 10-line findings.md that surfaces the next action for the loop.
---

# AlphaEdge Triage Skill

Run this at the start of any session or on a schedule to surface what needs to happen next.

## What it reads

1. `goals/README.md` — what phase is ACTIVE or next QUEUED
2. `git log --oneline -15` — recent commits and branch state
3. Last pytest output (if available in `backend/.pytest_cache/`)
4. `git status` — any uncommitted local state

## Output: findings.md (repo root, max 15 lines)

```
# Triage — <date>

## Active work
- Branch: <current>
- Last commit: <hash + message>
- Uncommitted: <files or "clean">

## Gate status
- pytest: PASS/FAIL/unknown
- typecheck: PASS/FAIL/unknown
- deploy: blocked by <reason> | green

## Next action
- <one sentence: what the loop should do next>

## Blockers (needs human)
- <anything that requires external action — secrets, GitHub settings>
```

## Rules
- Never modify code.
- If gates are unknown (can't run), say so — don't assume green.
- Blockers that need human action go in the last section. The loop cannot handle those.
