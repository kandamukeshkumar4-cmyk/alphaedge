# AlphaEdge Codex Instructions

These instructions apply inside `E:\polymarket clone`.

## Orchestration Constitution (binding for ALL agents)

**Read `orchestration/ORCHESTRATION.md` before your first edit.** It binds
every agent in this repo (Cursor, opencode/GLM, Claude Code, Codex, any model)
to the executor/advisor/verifier/gate seat system. The non-negotiables:

- Done = `py -3.13 orchestration/gate.py` exits 0, output PASTED in your
  report. A model saying "done" is a claim, not a proof.
- After 3 failed attempts at the same error: stop, write
  `orchestration/ESCALATION.md`, end the run. The advisor model (called at
  most once per task) answers escalations; executors implement.
- Delegation happens through JSON work orders
  (`task / files_in_scope / done_when / never / max_turns`).
- Do only what the work order names; extra scope is a defect. List unrelated
  findings, do not fix them.
- Deploy-affecting work must pass `py -3.13 scripts/verify_prod.py` against
  production, not localhost.
- Recurring chores log outcomes to `orchestration/trust_log.py`; standing
  invariants are re-verified by `orchestration/verify_goals.py`.

## Required Project Skills

- Read `.agents/skills/codex-first/SKILL.md` before delegating or accepting
  implementation work. Claude Code uses this skill to route hands-on
  implementation to Codex from a frozen work order, then reviews and verifies
  the result itself. Codex and other executor harnesses must treat it as routing
  policy only: do not self-delegate, do not skip verification, and keep every
  Codex prompt scoped to this repo, exact paths, constraints, non-goals, and
  proof commands.

## Automatic Skill Use

- Repo-local skills live in `.agents/skills/<skill-name>/SKILL.md`; Claude Code
  shims live in `.claude/skills/<skill-name>` and point back to the same folders.
- Before planning, coding, reviewing, researching, operating tooling, or writing
  handoff material, scan the `name` and `description` metadata in local
  `SKILL.md` files and load every skill that directly matches the task. The user
  should not need to type a slash command or explicitly say "use this skill."
- If multiple skills match, load the smallest relevant set. Process/orchestration
  skills apply before implementation or domain skills. Project guardrails in this
  file still override imported skill advice.
- Some imported skills are platform-specific or credential-specific, such as
  macOS, Pi, cmux, DeepAPI, browser CDP, or OpenRouter workflows. Use them only
  when the current task and environment actually match; otherwise state that the
  skill is not applicable and continue with the project-safe fallback.
- Treat `skills-lock.json` as the source inventory for vendored skill provenance
  and hash checks. Do not claim a skill came from a source unless the lock file
  or the skill folder proves it.

## Truth-First Defaults

- Treat user claims, diagnoses, and plans as unverified until checked against code, tests, logs, or documentation.
- Use direct verdicts when useful: `Correct`, `Incorrect`, `Partially correct`, `Unknown`, `Bad approach`, `Better approach available`.
- Do not implement changes that make the project less secure, less testable, or less maintainable without flagging the issue first.
- Keep changes small, reviewable, and tied to a test or explicit documentation update.

## AlphaEdge Scope Rules

- This is a paper-trading prediction market platform for NBA, broader sports, and election markets.
- All markets use simulated funds. Do not add cash funding, payment rails, or external execution language.
- `PAPER_TRADING_ONLY=true` is required in local, CI, and deploy contexts.
- LLM/agent code cannot submit raw orders. The only allowed path is `RiskService` -> validated `OrderIntent` -> `OrderBookService`.
- The canonical test market is `nba-2025-01-15-lal-bos`, Lakers vs Celtics, YES/NO, Lakers win resolves YES at `$1`.

## Execution Gates

- Week 1 gate: README, Docker db/redis/api, health endpoint, admin API key, CLOB, ledger, `domain_events`, admin market lifecycle, Lakers/Celtics tests.
- Week 2 gate: fixtures, workers, data quality, XGBoost, model/prediction lineage, backtest smoke.
- Week 3 gate: eval worker, Brier/calibration APIs, risk unit tests.
- Week 4 gate: LangGraph agents, guardrails, LLM judge, admin/proof dashboard.
- Week 5 gate: Railway/Vercel deployment, CI, live paper-run setup.

When preparing a PR, state which gate it claims and do not claim later gates unless verified by tests and runnable commands.

## Verification

- Backend: from `backend/`, run `uv run --extra dev pytest -q` and `uv run --extra dev ruff check app tests`.
- Frontend: from `frontend/`, run `npm run lint`, `npm run typecheck`, and `npm run build`.
- Docker: from repo root, run `docker compose up --build` for API/db/redis when Docker is available.

## PR and Task Goal Gates

For every AlphaEdge implementation, review, handoff, and merge goal, Codex must
classify and record these gates before claiming completion:

- Use the Superpowers `requesting-code-review` skill before merge, before final
  handoff, and after any major feature or subagent task. If the skill is not
  callable, do a manual diff review against the same standard and state that
  fallback explicitly.
- Use the GitHub `gh-address-comments` skill for any pull request before
  merging or claiming review feedback is handled. Resolve the PR from local git
  or the PR URL, inspect unresolved review threads, and address actionable
  feedback. Do not post replies, resolve threads, or submit reviews unless the
  user explicitly asks for that GitHub write.
- Use the global `bumblebee-supply-chain-scan` skill for dependency inventory
  and exposure checks. Run a standard project scan before merging and whenever
  package manifests, lockfiles, dependency loaders, or deployment images change;
  for docs-only or non-merge tasks, record why the scan is not applicable.

Do not merge a PR unless the current PR is unambiguous, not draft,
`mergeStateStatus` is `CLEAN`, `mergeable` is `MERGEABLE`, required checks and
project verification pass, review comments have no unresolved actionable
threads, and the worktree contains only intended changes.

## AutoLab Persistence Loop (every improvement ticket)

This applies to Codex, Cursor, and any agent working in this repo. It governs
any ticket whose job is to improve a working artifact — backtest accuracy,
Brier/calibration scores, deploy smoke-test resilience, risk-unit coverage, API
latency, or UX.

The AutoLab finding (long-horizon agents): success on long tasks is predicted by
persistence on the benchmark-edit-feedback loop, not by first-attempt quality.
Most models quit early or burned the budget with no progress; the ones that
sustained the loop (Claude Opus class among them) kept improving a
correct-but-suboptimal baseline for hours. Mirror that:

Bookmark/source: arXiv `2606.05080`, project site `https://autolab.moe/`, code
`https://github.com/autolabhq/autolab`, leaderboard
`https://autolab.moe/#leaderboard`. As of 2026-06-05, the paper abstract reports
17 evaluated models across 36 tasks, while public-site copy is inconsistent
between 7+ and 11+ model signals across 23 tasks; Claude Opus 4.6 is the
clearest strong signal. Verify the live leaderboard before model-selection
claims.

- **Start from a green baseline.** Begin from a passing gate (see Execution
  Gates) and the `verificationCommands` in `local.config.json`. Never trade
  correctness for a metric.
- **Define the benchmark first.** Use the relevant `verificationCommands` or a
  metric API (Brier, calibration, latency, deploy smoke pass-rate). Record the
  baseline measurement.
- **Iterate** measure -> edit -> re-measure -> fold the result into the next
  edit. Each edit is informed by the last measurement, not speculation.
- **Set an explicit budget** (iterations or wall-clock) and persist to it — do
  not hand off after one attempt.
- **Do not thrash.** Track best-so-far; after `K` consecutive no-progress
  iterations (default `K=3`), stop and reorganize or retire the direction.
- **Keep the best measured artifact.** Never hand off worse than baseline.

Guardrail: never game the benchmark, and never weaken `PAPER_TRADING_ONLY`, the
`RiskService -> OrderIntent -> OrderBookService` order path, or any deploy gate
to hit a metric. A benchmark win that regresses a gate or guardrail is a dead
end, not progress.

PR/handoff line for improvement tickets:

```text
AutoLab: baseline=<verified gate/measure> | benchmark=<metric/command> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
```

This line must include baseline, benchmark, iterations/best result, budget, and
outcome.

For a one-shot fix with no measurable axis, state "AutoLab: not applicable (no
iterative measure)".

## Quant Engine: Goals & Workflows

The Quant Engine roadmap (`docs/project/QUANT_ROADMAP.md`) is executed through a
status-tracked queue in `goals/` bound to reusable procedures in `workflows/`.
This is the default source of "what to build next" for this repo.

- **Start at `goals/README.md`.** Work the goal whose `status` is `ACTIVE` (one at
  a time; respect `depends_on`). Phase 0 (data connectors + snapshot store + CLV
  backtester) is already DONE; Phase 1 (`goals/phase-1-signals.md`) is ACTIVE.
- **Each goal binds to a workflow** (`workflows/backend-feature`, `ui-feature`, or
  `clv-model-gate`). Follow the bound workflow rather than re-deriving the process.
- **`workflows/clv-model-gate` is mandatory for any predictive model:** a model is
  shown as edge only if out-of-sample walk-forward CLV is positive AND its Brier
  beats the closing line. A model that fails to beat the closing line being hidden
  is a correct, honest outcome — not a failure to paper over.
- **On completion:** apply the Shared Definition of Done in `workflows/README.md`,
  update the goal's `status` in `goals/README.md`, record the PR/handoff line, and
  promote the next `QUEUED` goal to `ACTIVE`.
- These goals/workflows compose with the gates above (Execution Gates, PR/Task Goal
  Gates, AutoLab loop); they do not replace them. Never weaken `PAPER_TRADING_ONLY`,
  the `RiskService -> OrderIntent -> OrderBookService` path, or a deploy gate to
  close a goal.
