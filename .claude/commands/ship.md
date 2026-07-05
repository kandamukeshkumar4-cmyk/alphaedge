# /ship — Parallel Write + Test + Review

Orchestrates three subagents (writer, tester, reviewer) to implement, test, and review a task in parallel. You read one consolidated report at the end.

## Task
$ARGUMENTS

## How to run this

**Step 1 — Write the brief**
Before dispatching any agent, write a concise implementation brief covering:
- What to build / change (the "what")
- Acceptance criteria (how you know it's done)
- Files likely affected (based on a quick grep/glob)
- Constraints (security, performance, backwards-compat, test framework to use)

**Step 2 — Dispatch writer and tester in parallel**
Use the Agent tool to start BOTH at the same time:
- `writer` agent: give it the full brief, ask it to implement and return a Writer Report
- `tester` agent: give it the full brief, ask it to write tests from the spec (not the implementation) and return a Tester Report

**Step 3 — Dispatch reviewer after writer finishes**
Once the writer agent returns, dispatch the `reviewer` agent with:
- The original brief
- The list of changed files from the Writer Report
- Ask it to review the diff and return a Reviewer Report

**Step 4 — Consolidate and present**
After all three agents finish, output a single summary:

```
## Ship Report: <task one-liner>

### Writer Report
<paste writer's report>

### Tester Report
<paste tester's report>

### Reviewer Report
<paste reviewer's report>

### Overall Status
**Ready to commit?** YES / NO — <one sentence reason>
**Action needed:** <what the user must do next, e.g. "review critical issues in reviewer report" or "run tests and commit">
```

Do not commit or push. The user decides what to do after reading the report.
