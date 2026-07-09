# AlphaEdge — Claude Code Instructions

> The canonical agent rules for this repo live in `AGENTS.md`. Read it first.
> This file gives Claude Code the same context as Codex and Cursor in
> `E:\polymarket clone`.

## Orchestration Constitution (binding)

Read `orchestration/ORCHESTRATION.md` before your first edit. Key laws:
done = `py -3.13 orchestration/gate.py` exit 0 with output pasted; 3 failed
attempts at one error = write `orchestration/ESCALATION.md` and stop; the
advisor model is called at most once per task and never implements; extra
scope is a defect; deploy-affecting work must pass
`py -3.13 scripts/verify_prod.py` against production.

## Codex First Skill

Load `.agents/skills/codex-first/SKILL.md` for any non-trivial implementation,
refactor, bug fix, CI fix, dependency/tooling change, test-writing pass, or bulk
codebase exploration. Claude writes the spec/work order, delegates hands-on work
to Codex when the skill says to, and then performs the diff review and
verification itself. Do not delegate design judgment, destructive operations,
secrets/MCP work, releases, pushes, GitHub mutations, or review of Codex output.

## Automatic Skill Use

Repo-local skills are installed in `.agents/skills/<skill-name>/SKILL.md`.
Claude shims in `.claude/skills/<skill-name>` point to those same folders. Before
planning, coding, reviewing, researching, operating tools, or preparing a
handoff, match the task against local skill `name` and `description` metadata and
load the relevant skills automatically. The user should not need to invoke a
slash command. Load only the smallest relevant set, keep AGENTS.md guardrails
higher priority, and skip platform-specific skills unless the task and current
environment actually match them.

## Truth-First Defaults

- Treat user claims, diagnoses, and plans as unverified until checked against
  code, tests, logs, or documentation.
- Use direct verdicts when useful: `Correct`, `Incorrect`, `Partially correct`,
  `Unknown`, `Bad approach`, `Better approach available`.
- Do not implement changes that make the project less secure, less testable, or
  less maintainable without flagging the issue first.
- Keep changes small, reviewable, and tied to a test or explicit documentation
  update.

## Scope & Guardrails (non-negotiable)

- Paper-trading prediction market **simulation** for NBA, broader sports, and
  election markets. Simulated funds only — no cash funding, payment rails, or
  external execution language.
- `PAPER_TRADING_ONLY=true` is required in local, CI, and deploy contexts.
- LLM/agent code cannot submit raw orders. The only allowed path is
  `RiskService` → validated `OrderIntent` → `OrderBookService`.
- Canonical test market: `nba-2025-01-15-lal-bos`.

## Verification

- Backend (from `backend/`): `uv run --extra dev pytest -q` and
  `uv run --extra dev ruff check app tests`.
- Frontend (from `frontend/`): `npm run lint`, `npm run typecheck`,
  `npm run build`.
- State which Execution Gate (see `AGENTS.md`) a PR claims; do not claim later
  gates unless verified by tests and runnable commands.

## AutoLab Persistence Loop (every improvement ticket)

For any ticket that improves a working artifact (backtest accuracy,
Brier/calibration, deploy smoke resilience, risk-unit coverage, API latency, or
UX), run the AutoLab persistence loop defined in `AGENTS.md` → "AutoLab
Persistence Loop" and `.agents/skills/autolab-persistence-loop/SKILL.md`.

The finding (AutoLab, long-horizon agents): long-task success is predicted by
persistence on the benchmark-edit-feedback loop, not by first-attempt quality.
Start from a green baseline gate, define the benchmark (use `verificationCommands`
or a metric API), then iterate measure → edit → re-measure → fold in feedback
under an explicit budget. Persist to the budget, but stop and reorganize after
`K` consecutive no-progress iterations (default `K=3`). Keep the best measured
artifact; never hand off worse than baseline.

Guardrail: never game the benchmark, and never weaken `PAPER_TRADING_ONLY`, the
order path, or any deploy gate to hit a metric. Record the AutoLab handoff line:

```text
AutoLab: baseline=<verified gate/measure> | benchmark=<metric/command> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
```

For a one-shot fix with no measurable axis, state "AutoLab: not applicable (no
iterative measure)".
