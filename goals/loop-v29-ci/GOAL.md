# Loop V29 — CI hardening (GitHub Actions gates)

> Runner: ChatGPT/Codex IDE. Worktree E:/polymarket-worktrees/loop29-ci,
> branch loop29/ci. Constitution rules apply.

## Ownership
YOURS: NEW workflow files .github/workflows/ci-backend.yml, ci-frontend.yml,
ci-e2e.yml, goals/loop-v29-ci/**, and (only if needed) tiny additive tweaks
to package.json scripts / a CI helper script under scripts/ci/. FOREIGN —
NEVER EDIT: existing workflows (demo-uptime.yml, deploy-*.yml — the ops lane
owns them), backend/app/**, frontend/src/**.

## Requirements
- Trigger: push + pull_request to loop3-agent-memory and codex/alphaedge-base.
- ci-backend: uv sync, ADMIN_API_KEY=dev-admin-key pytest (fail on ANY
  failed test — surface the COUNT in the step summary), ruff, alembic
  single-head check. Cache uv. PAPER_TRADING_ONLY=true env.
- ci-frontend: npm ci, typecheck, lint --max-warnings=0, vitest, build.
  Cache node_modules/npm.
- ci-e2e: boot the local stack the way frontend/e2e/helpers does (uvicorn +
  isolated SQLite + next build+start), npx playwright test (chromium,
  --retries=1 max), upload the HTML report as an artifact on failure.
- All test-only secrets inline dev values; NO real secrets in workflows;
  never reference NEON/RAILWAY/VERCEL tokens.
- Keep each workflow under ~20 min (parallel jobs fine). Node 24 opt-in env
  + checkout@v6/setup-*@v6 per test_deploy_config.py workflow rules — READ
  that test first; your workflows must pass it.
- Docs: goals/loop-v29-ci/BRANCH-PROTECTION.md — recommended required checks
  (documentation only; do NOT change repo settings).

## Gate per ticket
Workflow YAML validated (actionlint if available, else careful review + the
deploy-config workflow test passing), backend pytest counts unchanged-green,
fresh verifier. Commits ci(loop29): <ticket>. Tickets: C1 backend, C2
frontend, C3 e2e, C4 branch-protection doc + full gate. STOP after C4.

## ORCHESTRATOR DIRECTIVE · DIR-V29-001 (binding, supersedes the advisor gate)
The Advisor requirement is WAIVED for this loop. Rationale: the advisor role
(design review before execution) is fulfilled by the loop orchestrator — this
GOAL.md is the advisor-approved spec, and every commit receives an
orchestrator review + independent gate before merge (see loop V15-V27
precedent in goals/). Do NOT attempt Claude Code CLI calls from this lane;
treat "advisor: not required (orchestrator-reviewed lane)" as satisfying the
orchestration policy, note DIR-V29-001 in your STATE.md loop log, and proceed
directly to C1 -> C4.
