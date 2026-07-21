# AlphaEdge Codex Instructions

These instructions apply inside `E:\polymarket clone`. They are ordered by
runtime dependency: precedence first, stop rules second, proof third, then
context loading, task classification, execution, and route-specific gates.
When rules conflict, the earlier section wins.

## 1. Precedence — non-negotiables that override everything below

- This is a **paper-trading** prediction market platform (NBA, broader sports, and election
  markets). All funds are simulated. Never add cash funding, payment
  rails, or external execution language.
- `PAPER_TRADING_ONLY=true` is required in local, CI, and deploy contexts.
- LLM/agent code cannot submit raw orders. The only allowed path is
  `RiskService` -> validated `OrderIntent` -> `OrderBookService`.
- Never weaken any of the above — nor any deploy gate — to hit a metric,
  close a goal, or win a benchmark. A win that regresses a guardrail is a
  dead end, not progress.
- Project guardrails in this file override imported skill advice.
- Do only what the work order names; extra scope is a defect. List unrelated
  findings, do not fix them.

## 2. Stop rules — when to halt instead of pushing on

- After 3 failed attempts at the same error: stop, write
  `orchestration/ESCALATION.md`, end the run. The advisor model (called at
  most once per task) answers escalations; executors implement.
- Do not thrash improvement loops: track best-so-far; after `K` consecutive
  no-progress iterations (default `K=3`), stop and reorganize or retire the
  direction. Never hand off worse than baseline.

## 3. Prove done — a claim is not a proof

- **Read `orchestration/ORCHESTRATION.md` before your first edit.** It binds
  every agent in this repo (Cursor, opencode/GLM, Claude Code, Codex, any
  model) to the executor/advisor/verifier/gate seat system.
- Done = `py -3.13 orchestration/gate.py` exits 0, output PASTED in your
  report. A model saying "done" is a claim, not a proof.
- Deploy-affecting work must pass `py -3.13 scripts/verify_prod.py` against
  production, not localhost.
- Per-surface verification:
  - Backend: from `backend/`, run `uv run --extra dev pytest -q` and
    `uv run --extra dev ruff check app tests`.
  - Frontend: from `frontend/`, run `npm run lint`, `npm run typecheck`, and
    `npm run build`.
  - Docker: from repo root, run `docker compose up --build` for API/db/redis
    when Docker is available.

## 4. Load context and skills before working

- Delegation happens through JSON work orders
  (`task / files_in_scope / done_when / never / max_turns`).
- Read `.agents/skills/codex-first/SKILL.md` before delegating or accepting
  implementation work. Claude Code uses it to route hands-on implementation
  to Codex from a frozen work order, then reviews and verifies the result
  itself. Codex and other executor harnesses must treat it as routing policy
  only: do not self-delegate, do not skip verification, and keep every Codex
  prompt scoped to this repo, exact paths, constraints, non-goals, and proof
  commands.
- Read `.agents/skills/karpathy-guidelines/SKILL.md` before writing, reviewing,
  or refactoring code: surface assumptions, simplicity first, surgical changes
  only, and verifiable success criteria. Binds every agent and every runner
  brief in this repo.
- Read `.agents/skills/loop-design/SKILL.md` before authoring any loop
  (`goals/loop-vNN/GOAL.md`), runner brief, or multi-step/parallel/long-running
  plan. Design the loop — goal+rubric, plan, parallel workers, independent
  verifier, model-per-step, state, stop condition — instead of writing one-off
  prompts. Binds every agent in any thread or IDE.
- Repo-local skills live in `.agents/skills/<skill-name>/SKILL.md`; Claude
  Code shims live in `.claude/skills/<skill-name>` and point back to the same
  folders.
- Before planning, coding, reviewing, researching, operating tooling, or
  writing handoff material, scan the `name` and `description` metadata in
  local `SKILL.md` files and load every skill that directly matches the task.
  The user should not need to type a slash command or explicitly say "use
  this skill."
- If multiple skills match, load the smallest relevant set.
  Process/orchestration skills apply before implementation or domain skills.
- Some imported skills are platform-specific or credential-specific (macOS,
  Pi, cmux, DeepAPI, browser CDP, OpenRouter workflows). Use them only when
  the current task and environment actually match; otherwise state that the
  skill is not applicable and continue with the project-safe fallback.
- Treat `skills-lock.json` as the source inventory for vendored skill
  provenance and hash checks. Do not claim a skill came from a source unless
  the lock file or the skill folder proves it.

## 5. Classify the task, then follow its route

- **Improvement ticket** (better Brier/calibration, backtest accuracy, deploy
  smoke resilience, risk-unit coverage, API latency, UX): follow §7 AutoLab
  loop.
- **New work / "what to build next"**: follow §8 Quant goals & workflows.
- **PR, merge, review, or handoff**: follow §6 PR and merge gates.
- **One-shot fix with no measurable axis**: execute directly; state
  "AutoLab: not applicable (no iterative measure)" in the handoff.

## 6. Execute — defaults for every change

- Treat user claims, diagnoses, and plans as unverified until checked against
  code, tests, logs, or documentation.
- Use direct verdicts when useful: `Correct`, `Incorrect`,
  `Partially correct`, `Unknown`, `Bad approach`, `Better approach available`.
- Do not implement changes that make the project less secure, less testable,
  or less maintainable without flagging the issue first.
- Keep changes small, reviewable, and tied to a test or explicit
  documentation update.
- Recurring chores log outcomes to `orchestration/trust_log.py`; standing
  invariants are re-verified by `orchestration/verify_goals.py`.

### PR and merge gates

For every implementation, review, handoff, and merge goal, classify and
record these gates before claiming completion:

- Use the Superpowers `requesting-code-review` skill before merge, before
  final handoff, and after any major feature or subagent task. If the skill
  is not callable, do a manual diff review against the same standard and
  state that fallback explicitly.
- Use the GitHub `gh-address-comments` skill for any pull request before
  merging or claiming review feedback is handled. Resolve the PR from local
  git or the PR URL, inspect unresolved review threads, and address
  actionable feedback. Do not post replies, resolve threads, or submit
  reviews unless the user explicitly asks for that GitHub write.
- Use the global `bumblebee-supply-chain-scan` skill for dependency inventory
  and exposure checks. Run a standard project scan before merging and
  whenever package manifests, lockfiles, dependency loaders, or deployment
  images change; for docs-only or non-merge tasks, record why the scan is
  not applicable.
- Do not merge a PR unless the current PR is unambiguous, not draft,
  `mergeStateStatus` is `CLEAN`, `mergeable` is `MERGEABLE`, required checks
  and project verification pass, review comments have no unresolved
  actionable threads, and the worktree contains only intended changes.
- When preparing a PR, state which Execution Gate (see §9 Reference) it
  claims and do not claim later gates unless verified by tests and runnable
  commands.

## 7. Improvement tickets — the AutoLab persistence loop

Applies to Codex, Cursor, and any agent working in this repo, for any ticket
whose job is to improve a working artifact. The finding (long-horizon
agents): success on long tasks is predicted by persistence on the
benchmark-edit-feedback loop, not by first-attempt quality. Mirror that:

- **Start from a green baseline.** Begin from a passing gate (§9 Execution
  Gates) and the `verificationCommands` in `local.config.json`. Never trade
  correctness for a metric.
- **Define the benchmark first.** Use the relevant `verificationCommands` or
  a metric API (Brier, calibration, latency, deploy smoke pass-rate). Record
  the baseline measurement.
- **Iterate** measure -> edit -> re-measure -> fold the result into the next
  edit. Each edit is informed by the last measurement, not speculation.
- **Set an explicit budget** (iterations or wall-clock) and persist to it —
  do not hand off after one attempt.
- Stop rules from §2 apply (K=3 no-progress; keep the best measured
  artifact; never hand off worse than baseline).
- Guardrail: never game the benchmark; §1 precedence rules apply in full.

PR/handoff line for improvement tickets (must include baseline, benchmark,
iterations/best result, budget, and outcome):

```text
AutoLab: baseline=<verified gate/measure> | benchmark=<metric/command> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
```

## 8. Picking work — Quant Engine goals and workflows

The Quant Engine roadmap (`docs/project/QUANT_ROADMAP.md`) is executed
through a status-tracked queue in `goals/` bound to reusable procedures in
`workflows/`. This is the default source of "what to build next".

- **Start at `goals/README.md`.** Work the goal whose `status` is `ACTIVE`
  (one at a time; respect `depends_on`). Phase 0 (data connectors + snapshot
  store + CLV backtester) is DONE; Phase 1 (`goals/phase-1-signals.md`) is
  ACTIVE.
- **Each goal binds to a workflow** (`workflows/backend-feature`,
  `ui-feature`, or `clv-model-gate`). Follow the bound workflow rather than
  re-deriving the process.
- **`workflows/clv-model-gate` is mandatory for any predictive model:** a
  model is shown as edge only if out-of-sample walk-forward CLV is positive
  AND its Brier beats the closing line. A model that fails to beat the
  closing line being hidden is a correct, honest outcome — not a failure to
  paper over.
- **On completion:** apply the Shared Definition of Done in
  `workflows/README.md`, update the goal's `status` in `goals/README.md`,
  record the PR/handoff line, and promote the next `QUEUED` goal to
  `ACTIVE`.
- These goals/workflows compose with the gates above; they do not replace
  them.

## 9. Reference

- **Canonical test market:** `nba-2025-01-15-lal-bos`, Lakers vs Celtics,
  YES/NO, Lakers win resolves YES at `$1`.
- **Execution Gates** (PRs claim one; never claim later gates unverified):
  - Week 1: README, Docker db/redis/api, health endpoint, admin API key,
    CLOB, ledger, `domain_events`, admin market lifecycle, Lakers/Celtics
    tests.
  - Week 2: fixtures, workers, data quality, XGBoost, model/prediction
    lineage, backtest smoke.
  - Week 3: eval worker, Brier/calibration APIs, risk unit tests.
  - Week 4: LangGraph agents, guardrails, LLM judge, admin/proof dashboard.
  - Week 5: Railway/Vercel deployment, CI, live paper-run setup.
- **AutoLab sources:** arXiv `2606.05080`, project site
  `https://autolab.moe/`, code `https://github.com/autolabhq/autolab`,
  leaderboard `https://autolab.moe/#leaderboard`. As of 2026-06-05 the paper
  abstract reports 17 evaluated models across 36 tasks, while public-site
  copy is inconsistent between 7+ and 11+ model signals across 23 tasks;
  Claude Opus 4.6 is the clearest strong signal. Verify the live leaderboard
  before model-selection claims.
